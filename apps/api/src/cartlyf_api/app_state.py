from dramatiq.brokers.redis import RedisBroker
from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine

from cartlyf_api.email.provider import EmailProvider
from cartlyf_api.settings import Settings
from cartlyf_api.solves.notifier import SolveNotifier
from cartlyf_api.storage import ObjectStore


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


def engine_of(request: Request) -> AsyncEngine:
    return request.app.state.db_engine


def redis_of(request: Request) -> Redis:
    return request.app.state.redis


def email_provider_of(request: Request) -> EmailProvider:
    return request.app.state.email_provider


def object_store_of(request: Request) -> ObjectStore:
    return request.app.state.object_store


def broker_of(request: Request) -> RedisBroker:
    return request.app.state.broker


def solve_notifier_of(request: Request) -> SolveNotifier:
    return request.app.state.solve_notifier
