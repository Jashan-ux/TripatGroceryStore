import warnings
from types import SimpleNamespace

from app.db.alembic_utils import include_object
from app.models import Base, Product, ProductVariant, Profile, StoreSettings
from sqlalchemy import BigInteger, DateTime


def foreign_key(target: str) -> SimpleNamespace:
    return SimpleNamespace(elements=[SimpleNamespace(target_fullname=target)])


def test_reflected_supabase_auth_foreign_key_is_excluded_from_autogenerate() -> None:
    assert not include_object(
        foreign_key("auth.users.id"),
        "fk_profiles_auth_user",
        "foreign_key_constraint",
        True,
        None,
    )


def test_public_foreign_keys_remain_in_autogenerate() -> None:
    assert include_object(
        foreign_key("public.products.id"),
        "fk_order_items_product_id_products",
        "foreign_key_constraint",
        True,
        None,
    )


def test_model_objects_are_not_excluded() -> None:
    assert include_object(
        foreign_key("auth.users.id"),
        "fk_profiles_auth_user",
        "foreign_key_constraint",
        False,
        None,
    )


def test_non_foreign_key_objects_are_not_excluded() -> None:
    assert include_object(SimpleNamespace(), "profiles", "table", True, None)


def test_paise_columns_keep_bigint_and_profile_timestamp_is_timezone_aware() -> None:
    for model in (Product, ProductVariant, StoreSettings):
        paise_columns = [
            column for column in model.__table__.columns if column.name.endswith("_paise")
        ]
        assert paise_columns
        assert all(isinstance(column.type, BigInteger) for column in paise_columns)

    last_seen_at = Profile.__table__.c.last_seen_at.type
    assert isinstance(last_seen_at, DateTime)
    assert last_seen_at.timezone is True


def test_deferred_wallet_cycle_has_an_orderable_metadata_graph() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        list(Base.metadata.sorted_tables)

    assert not any("unresolvable cycles" in str(warning.message) for warning in caught)
