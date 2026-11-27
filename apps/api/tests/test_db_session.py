from app.db.session import _engine_kwargs


def test_transaction_pooler_disables_prepared_statement_caches() -> None:
    connect_args = _engine_kwargs()["connect_args"]

    assert connect_args["statement_cache_size"] == 0
    assert connect_args["prepared_statement_cache_size"] == 0

    name_factory = connect_args["prepared_statement_name_func"]
    assert callable(name_factory)
    first_name = name_factory()
    second_name = name_factory()
    assert first_name.startswith("__asyncpg_") and first_name.endswith("__")
    assert second_name.startswith("__asyncpg_") and second_name.endswith("__")
    assert first_name != second_name
