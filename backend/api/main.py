from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .routes.auth import router as auth_router
from .routes.ai_providers import router as ai_providers_router
from .routes.compose import router as compose_router
from .routes.designs import router as designs_router
from .routes.export import router as export_router
from .routes.files import router as files_router
from .routes.generate import router as generate_router
from .routes.materials import router as materials_router
from .routes.prj_templates import router as prj_templates_router
from .routes.prompt_templates import router as prompt_templates_router
from .routes.roles import router as roles_router
from .routes.upload import router as upload_router
from .routes.users import router as users_router
from .routes.variants import router as variants_router
from .db.base import get_session
from .db.seed_users import seed_test_users
from .db.seed_prompt_templates import seed_prompt_templates
from .middleware.errors import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from .middleware.logging import RequestLoggingMiddleware, configure_logging
from .rbac.seed import seed_default_roles
from .admin import create_admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    from taskiq_app import broker
    
    configure_logging(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.info("Starting Clothes Design API...")
    
    await broker.startup()
    
    try:
        async for session in get_session():
            try:
                logger.info("Seeding default roles...")
                await seed_default_roles(session)
                logger.info("Seeding test users...")
                await seed_test_users(session)
                logger.info("Seeding prompt templates...")
                await seed_prompt_templates(session)
                logger.info("Committing seeds...")
                await session.commit()
                logger.info("Database seeding complete")
            except Exception as exc:
                logger.error("Seeding failed: %s", exc, exc_info=True)
                await session.rollback()
                raise
            finally:
                break
    except Exception as exc:
        logger.error("Lifespan startup failed: %s", exc, exc_info=True)
        raise
    yield
    logger.info("Shutting down Clothes Design API...")
    await broker.shutdown()


# Create FastAPI app
app = FastAPI(
    title="Clothes Design API",
    description="API for clothes design platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

add_pagination(app)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "message": "Welcome to Clothes Design API",
        "version": "0.1.0",
    }


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(upload_router)
app.include_router(materials_router)
app.include_router(prj_templates_router)
app.include_router(prompt_templates_router)
app.include_router(generate_router)
app.include_router(variants_router)
app.include_router(designs_router)
app.include_router(compose_router)
app.include_router(export_router)
app.include_router(ai_providers_router)
app.include_router(files_router)

admin = create_admin()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")
admin.mount_to(app)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
