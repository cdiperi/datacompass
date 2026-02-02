"""Exception handlers for the API layer."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from datacompass.core.adapters.exceptions import AdapterError, AdapterNotFoundError
from datacompass.core.services import (
    ObjectNotFoundError,
    SourceExistsError,
    SourceNotFoundError,
)
from datacompass.core.services.deprecation_service import (
    CampaignExistsError,
    CampaignNotFoundError,
    DeprecationNotFoundError,
    ObjectAlreadyDeprecatedError,
)
from datacompass.core.services.dq_service import (
    DQBreachNotFoundError,
    DQConfigExistsError,
    DQConfigNotFoundError,
    DQExpectationNotFoundError,
)
from datacompass.core.services.notification_service import (
    ChannelExistsError,
    ChannelNotFoundError,
    RuleNotFoundError,
)
from datacompass.core.services.scheduling_service import (
    ScheduleExistsError,
    ScheduleNotFoundError,
)


async def source_not_found_handler(request: Request, exc: SourceNotFoundError) -> JSONResponse:
    """Handle SourceNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "source_not_found",
            "message": str(exc),
            "detail": {"source_name": exc.name},
        },
    )


async def source_exists_handler(request: Request, exc: SourceExistsError) -> JSONResponse:
    """Handle SourceExistsError exceptions."""
    return JSONResponse(
        status_code=409,
        content={
            "error": "source_exists",
            "message": str(exc),
            "detail": {"source_name": exc.name},
        },
    )


async def object_not_found_handler(request: Request, exc: ObjectNotFoundError) -> JSONResponse:
    """Handle ObjectNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "object_not_found",
            "message": str(exc),
            "detail": {"identifier": exc.identifier},
        },
    )


async def adapter_not_found_handler(request: Request, exc: AdapterNotFoundError) -> JSONResponse:
    """Handle AdapterNotFoundError exceptions."""
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_source_type",
            "message": str(exc),
            "detail": {"source_type": exc.source_type},
        },
    )


async def adapter_error_handler(request: Request, exc: AdapterError) -> JSONResponse:
    """Handle general AdapterError exceptions."""
    return JSONResponse(
        status_code=502,
        content={
            "error": "adapter_error",
            "message": exc.message,
            "detail": {"source_type": exc.source_type} if exc.source_type else None,
        },
    )


async def dq_config_not_found_handler(
    request: Request, exc: DQConfigNotFoundError
) -> JSONResponse:
    """Handle DQConfigNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "dq_config_not_found",
            "message": str(exc),
            "detail": {"identifier": str(exc.identifier)},
        },
    )


async def dq_config_exists_handler(
    request: Request, exc: DQConfigExistsError
) -> JSONResponse:
    """Handle DQConfigExistsError exceptions."""
    return JSONResponse(
        status_code=409,
        content={
            "error": "dq_config_exists",
            "message": str(exc),
            "detail": {"object_id": exc.object_id},
        },
    )


async def dq_expectation_not_found_handler(
    request: Request, exc: DQExpectationNotFoundError
) -> JSONResponse:
    """Handle DQExpectationNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "dq_expectation_not_found",
            "message": str(exc),
            "detail": {"identifier": exc.identifier},
        },
    )


async def dq_breach_not_found_handler(
    request: Request, exc: DQBreachNotFoundError
) -> JSONResponse:
    """Handle DQBreachNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "dq_breach_not_found",
            "message": str(exc),
            "detail": {"identifier": exc.identifier},
        },
    )


async def campaign_not_found_handler(
    request: Request, exc: CampaignNotFoundError
) -> JSONResponse:
    """Handle CampaignNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "campaign_not_found",
            "message": str(exc),
            "detail": {"identifier": str(exc.identifier)},
        },
    )


async def campaign_exists_handler(
    request: Request, exc: CampaignExistsError
) -> JSONResponse:
    """Handle CampaignExistsError exceptions."""
    return JSONResponse(
        status_code=409,
        content={
            "error": "campaign_exists",
            "message": str(exc),
            "detail": {"source_id": exc.source_id, "name": exc.name},
        },
    )


async def deprecation_not_found_handler(
    request: Request, exc: DeprecationNotFoundError
) -> JSONResponse:
    """Handle DeprecationNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "deprecation_not_found",
            "message": str(exc),
            "detail": {"identifier": exc.identifier},
        },
    )


async def object_already_deprecated_handler(
    request: Request, exc: ObjectAlreadyDeprecatedError
) -> JSONResponse:
    """Handle ObjectAlreadyDeprecatedError exceptions."""
    return JSONResponse(
        status_code=409,
        content={
            "error": "object_already_deprecated",
            "message": str(exc),
            "detail": {"campaign_id": exc.campaign_id, "object_id": exc.object_id},
        },
    )


async def schedule_not_found_handler(
    request: Request, exc: ScheduleNotFoundError
) -> JSONResponse:
    """Handle ScheduleNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "schedule_not_found",
            "message": str(exc),
            "detail": {"identifier": str(exc.identifier)},
        },
    )


async def schedule_exists_handler(
    request: Request, exc: ScheduleExistsError
) -> JSONResponse:
    """Handle ScheduleExistsError exceptions."""
    return JSONResponse(
        status_code=409,
        content={
            "error": "schedule_exists",
            "message": str(exc),
            "detail": {"name": exc.name},
        },
    )


async def channel_not_found_handler(
    request: Request, exc: ChannelNotFoundError
) -> JSONResponse:
    """Handle ChannelNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "channel_not_found",
            "message": str(exc),
            "detail": {"identifier": str(exc.identifier)},
        },
    )


async def channel_exists_handler(
    request: Request, exc: ChannelExistsError
) -> JSONResponse:
    """Handle ChannelExistsError exceptions."""
    return JSONResponse(
        status_code=409,
        content={
            "error": "channel_exists",
            "message": str(exc),
            "detail": {"name": exc.name},
        },
    )


async def rule_not_found_handler(
    request: Request, exc: RuleNotFoundError
) -> JSONResponse:
    """Handle RuleNotFoundError exceptions."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "rule_not_found",
            "message": str(exc),
            "detail": {"identifier": str(exc.identifier)},
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(SourceNotFoundError, source_not_found_handler)
    app.add_exception_handler(SourceExistsError, source_exists_handler)
    app.add_exception_handler(ObjectNotFoundError, object_not_found_handler)
    app.add_exception_handler(AdapterNotFoundError, adapter_not_found_handler)
    app.add_exception_handler(AdapterError, adapter_error_handler)
    app.add_exception_handler(DQConfigNotFoundError, dq_config_not_found_handler)
    app.add_exception_handler(DQConfigExistsError, dq_config_exists_handler)
    app.add_exception_handler(DQExpectationNotFoundError, dq_expectation_not_found_handler)
    app.add_exception_handler(DQBreachNotFoundError, dq_breach_not_found_handler)
    app.add_exception_handler(CampaignNotFoundError, campaign_not_found_handler)
    app.add_exception_handler(CampaignExistsError, campaign_exists_handler)
    app.add_exception_handler(DeprecationNotFoundError, deprecation_not_found_handler)
    app.add_exception_handler(ObjectAlreadyDeprecatedError, object_already_deprecated_handler)
    app.add_exception_handler(ScheduleNotFoundError, schedule_not_found_handler)
    app.add_exception_handler(ScheduleExistsError, schedule_exists_handler)
    app.add_exception_handler(ChannelNotFoundError, channel_not_found_handler)
    app.add_exception_handler(ChannelExistsError, channel_exists_handler)
    app.add_exception_handler(RuleNotFoundError, rule_not_found_handler)
