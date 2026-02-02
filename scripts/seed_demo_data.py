#!/usr/bin/env python3
"""Seed demo data for local development.

Usage:
    python scripts/seed_demo_data.py          # Create demo data if not exists
    python scripts/seed_demo_data.py --reset  # Delete and recreate demo data
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from datacompass.core.models import Base, DataSource, CatalogObject, Column, Dependency
from datacompass.core.repositories.search import SearchRepository
from datacompass.config import get_settings


def seed_demo_data(reset: bool = False):
    """Create demo sources, objects, and columns."""
    settings = get_settings()
    settings.ensure_data_dir()
    engine = create_engine(settings.resolved_database_url)

    # Create tables if they don't exist
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Check if demo data already exists
        existing = session.query(DataSource).filter_by(name="demo").first()
        if existing:
            if reset:
                print("Resetting demo data...")
                # Delete the source (cascades to objects, columns, dependencies)
                session.delete(existing)
                session.commit()
                # Clear FTS entries for demo source
                session.execute(
                    text("DELETE FROM catalog_fts WHERE source_name = 'demo'")
                )
                session.commit()
                print("Existing demo data deleted.")
            else:
                print("Demo data already exists. Use --reset to recreate.")
                return

        # Create demo source
        demo_source = DataSource(
            name="demo",
            display_name="Demo Database",
            source_type="databricks",
            is_active=True,
            connection_info={"host": "demo.cloud.databricks.com", "catalog": "main"},
            last_scan_status="success",
        )
        session.add(demo_source)
        session.flush()  # Get the ID

        # Demo objects with realistic names
        objects_data = [
            # Core tables
            ("core", "users", "TABLE", "User accounts and profile information", ["pii", "core"]),
            ("core", "orders", "TABLE", "Customer orders with status tracking", ["core", "financial"]),
            ("core", "products", "TABLE", "Product catalog with pricing", ["core"]),
            ("core", "customers", "TABLE", "Customer master data", ["pii", "core"]),
            ("core", "payments", "TABLE", "Payment transactions", ["pii", "financial"]),

            # Analytics tables
            ("analytics", "daily_sales", "TABLE", "Aggregated daily sales metrics", ["analytics"]),
            ("analytics", "user_sessions", "TABLE", "User session tracking data", ["analytics"]),
            ("analytics", "funnel_metrics", "TABLE", "Conversion funnel metrics", ["analytics"]),

            # Views
            ("reporting", "active_users_v", "VIEW", "Active users in the last 30 days", ["reporting"]),
            ("reporting", "revenue_by_product_v", "VIEW", "Revenue breakdown by product", ["reporting", "financial"]),
            ("reporting", "customer_lifetime_value_v", "VIEW", "CLV calculations per customer", ["reporting"]),

            # Staging tables
            ("staging", "raw_events", "TABLE", "Raw event stream data", ["staging"]),
            ("staging", "raw_transactions", "TABLE", "Raw transaction imports", ["staging"]),
        ]

        # Columns for each object type
        user_columns = [
            ("id", "BIGINT", False, "Primary key"),
            ("email", "VARCHAR(255)", False, "User email address"),
            ("name", "VARCHAR(100)", True, "Display name"),
            ("created_at", "TIMESTAMP", False, "Account creation timestamp"),
            ("updated_at", "TIMESTAMP", False, "Last update timestamp"),
            ("is_active", "BOOLEAN", False, "Whether account is active"),
        ]

        order_columns = [
            ("id", "BIGINT", False, "Primary key"),
            ("user_id", "BIGINT", False, "Foreign key to users"),
            ("status", "VARCHAR(50)", False, "Order status"),
            ("total_amount", "DECIMAL(10,2)", False, "Order total"),
            ("created_at", "TIMESTAMP", False, "Order creation time"),
            ("shipped_at", "TIMESTAMP", True, "Shipping timestamp"),
        ]

        product_columns = [
            ("id", "BIGINT", False, "Primary key"),
            ("sku", "VARCHAR(50)", False, "Stock keeping unit"),
            ("name", "VARCHAR(200)", False, "Product name"),
            ("price", "DECIMAL(10,2)", False, "Unit price"),
            ("category", "VARCHAR(100)", True, "Product category"),
        ]

        generic_columns = [
            ("id", "BIGINT", False, "Primary key"),
            ("created_at", "TIMESTAMP", False, "Creation timestamp"),
            ("data", "JSON", True, "JSON payload"),
        ]

        for schema, name, obj_type, description, tags in objects_data:
            obj = CatalogObject(
                source_id=demo_source.id,
                schema_name=schema,
                object_name=name,
                object_type=obj_type,
                source_metadata={"row_count": 10000, "size_bytes": 1024000},
                user_metadata={"description": description, "tags": tags},
            )
            session.add(obj)
            session.flush()

            # Add columns based on object name
            if name == "users":
                cols = user_columns
            elif name == "orders":
                cols = order_columns
            elif name == "products":
                cols = product_columns
            else:
                cols = generic_columns

            for i, (col_name, data_type, nullable, col_desc) in enumerate(cols):
                col = Column(
                    object_id=obj.id,
                    column_name=col_name,
                    position=i,
                    source_metadata={"data_type": data_type, "nullable": nullable},
                    user_metadata={"description": col_desc},
                )
                session.add(col)

        session.commit()
        print(f"Created demo source with {len(objects_data)} objects")

        # Build lookup for object IDs by name
        obj_lookup = {}
        for obj in session.query(CatalogObject).filter_by(source_id=demo_source.id).all():
            obj_lookup[f"{obj.schema_name}.{obj.object_name}"] = obj.id

        # Define lineage relationships (dependent -> dependencies)
        # Format: (dependent_object, [list of objects it depends on])
        lineage_data = [
            # Staging feeds into core
            # (no upstream for staging - they're source tables)

            # Core tables have some relationships
            ("core.orders", ["core.users", "core.customers", "core.products"]),
            ("core.payments", ["core.orders"]),

            # Analytics depends on core and staging
            ("analytics.daily_sales", ["core.orders", "core.products"]),
            ("analytics.user_sessions", ["staging.raw_events", "core.users"]),
            ("analytics.funnel_metrics", ["analytics.user_sessions", "core.users"]),

            # Reporting views depend on core and analytics
            ("reporting.active_users_v", ["core.users", "analytics.user_sessions"]),
            ("reporting.revenue_by_product_v", ["core.orders", "core.products", "analytics.daily_sales"]),
            ("reporting.customer_lifetime_value_v", ["core.customers", "core.orders", "core.payments"]),
        ]

        dep_count = 0
        for dependent, targets in lineage_data:
            dependent_id = obj_lookup.get(dependent)
            if not dependent_id:
                print(f"Warning: {dependent} not found")
                continue

            for target in targets:
                target_id = obj_lookup.get(target)
                if not target_id:
                    print(f"Warning: {target} not found")
                    continue

                dep = Dependency(
                    source_id=demo_source.id,
                    object_id=dependent_id,
                    target_id=target_id,
                    dependency_type="DIRECT",
                    parsing_source="source_metadata",
                    confidence="HIGH",
                )
                session.add(dep)
                dep_count += 1

        # Add one external dependency example
        clv_view_id = obj_lookup.get("reporting.customer_lifetime_value_v")
        if clv_view_id:
            ext_dep = Dependency(
                source_id=demo_source.id,
                object_id=clv_view_id,
                target_id=None,  # External reference
                target_external={
                    "schema": "external_crm",
                    "name": "customer_segments",
                    "type": "TABLE",
                },
                dependency_type="DIRECT",
                parsing_source="source_metadata",
                confidence="MEDIUM",
            )
            session.add(ext_dep)
            dep_count += 1

        session.commit()
        print(f"Created {dep_count} dependency relationships")

        # Reindex for search
        search_repo = SearchRepository(session)
        count = search_repo.reindex_all()
        print(f"Indexed {count} objects for search")

        print("\nDemo data seeded successfully!")
        print("Start the API server: .venv/bin/uvicorn datacompass.api:app --reload")
        print("Start the frontend: cd frontend && npm run dev")
        print("Open: http://localhost:5173")


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    seed_demo_data(reset=reset_flag)
