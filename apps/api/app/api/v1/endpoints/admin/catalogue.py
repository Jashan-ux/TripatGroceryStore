"""The owner's catalogue: products, categories, brands, bulk add and images.

Every route is behind ``AdminUserDep`` and every mutation ends in exactly one
``commit`` here rather than inside a service — that is what lets the bulk importer
be genuinely all-or-nothing: the services only flush, and this layer decides when
the transaction becomes real.
"""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Path, Query, UploadFile, status

from app.api.deps import AdminUserDep, SessionDep
from app.core.errors import ValidationError
from app.repositories import admin_tools as repo
from app.schemas.admin_catalogue import (
    AdminCategoryListOut,
    AdminProductListOut,
    BrandAdminOut,
    BrandDeleteOut,
    BrandIn,
    BrandListOut,
    BrandUpdateIn,
    BulkIn,
    BulkResultOut,
    CategoryAdminOut,
    CategoryDeleteOut,
    CategoryIn,
    CategoryUpdateIn,
    ImageOut,
    ProductAdminOut,
    ProductCreateIn,
    ProductDeleteOut,
    ProductUpdateIn,
)
from app.services import admin_catalogue as service
from app.services import bulk_import, uploads

router = APIRouter(prefix="/admin/catalogue", tags=["admin"])

ProductId = Annotated[uuid.UUID, Path(description="Product id")]
CategoryId = Annotated[uuid.UUID, Path(description="Category id")]
BrandId = Annotated[uuid.UUID, Path(description="Brand id")]


@router.get("/products", response_model=AdminProductListOut, summary="Search the catalogue you own")
async def list_products(
    _: AdminUserDep,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=120, description="Name or slug")] = None,
    category_id: uuid.UUID | None = None,
    brand_id: uuid.UUID | None = None,
    include_inactive: Annotated[bool, Query(description="Also show hidden products")] = False,
    low_stock: Annotated[bool, Query(description="Only rows at or below their threshold")] = False,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminProductListOut:
    rows, total = await repo.list_products_admin(
        session,
        q=q,
        category_id=category_id,
        brand_id=brand_id,
        only_inactive=include_inactive,
        low_stock=low_stock,
        page=page,
        page_size=page_size,
    )
    return AdminProductListOut(
        items=[service.product_out(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/products/{product_id}", response_model=ProductAdminOut, summary="One product")
async def get_product(
    _: AdminUserDep, session: SessionDep, product_id: ProductId
) -> ProductAdminOut:
    product = await repo.get_product_admin(session, product_id)
    if product is None:
        from app.core.errors import NotFoundError

        raise NotFoundError("That product does not exist.", code="product_not_found")
    return service.product_out(product)


@router.post(
    "/products",
    response_model=ProductAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a product (the inline category row uses this)",
)
async def create_product(
    user: AdminUserDep, session: SessionDep, payload: ProductCreateIn
) -> ProductAdminOut:
    product = await service.create_product(session, user.profile, payload)
    await session.commit()
    fresh = await repo.get_product_admin(session, product.id)
    assert fresh is not None
    return service.product_out(fresh)


@router.patch("/products/{product_id}", response_model=ProductAdminOut, summary="Edit a product")
async def update_product(
    user: AdminUserDep, session: SessionDep, product_id: ProductId, payload: ProductUpdateIn
) -> ProductAdminOut:
    product = await service.update_product(session, user.profile, product_id, payload)
    await session.commit()
    fresh = await repo.get_product_admin(session, product.id)
    assert fresh is not None
    return service.product_out(fresh)


@router.delete(
    "/products/{product_id}",
    response_model=ProductDeleteOut,
    summary="Delete a product, or hide it when orders reference it",
)
async def delete_product(
    user: AdminUserDep, session: SessionDep, product_id: ProductId
) -> ProductDeleteOut:
    outcome, message = await service.delete_product(session, user.profile, product_id)
    await session.commit()
    return ProductDeleteOut(
        id=product_id,
        outcome="deleted" if outcome == "deleted" else "deactivated",
        message=message,
    )


@router.post(
    "/products/bulk",
    response_model=BulkResultOut,
    summary="Add many products from a CSV, all or nothing",
)
async def bulk_add(user: AdminUserDep, session: SessionDep, payload: BulkIn) -> BulkResultOut:
    result = await bulk_import.run(
        session, user.profile, csv_text=payload.csv, dry_run=payload.dry_run
    )
    if result.committed:
        await session.commit()
    return result


@router.get(
    "/categories", response_model=AdminCategoryListOut, summary="Every category and subcategory"
)
async def list_categories(_: AdminUserDep, session: SessionDep) -> AdminCategoryListOut:
    return AdminCategoryListOut(categories=await service.category_list(session))


@router.post(
    "/categories",
    response_model=CategoryAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a category or subcategory",
)
async def create_category(
    user: AdminUserDep, session: SessionDep, payload: CategoryIn
) -> CategoryAdminOut:
    created = await service.create_category(session, user.profile, payload)
    await session.commit()
    rows = await service.category_list(session)
    return next(row for row in rows if row.id == created.id)


@router.patch(
    "/categories/{category_id}", response_model=CategoryAdminOut, summary="Edit a category"
)
async def update_category(
    user: AdminUserDep, session: SessionDep, category_id: CategoryId, payload: CategoryUpdateIn
) -> CategoryAdminOut:
    updated = await service.update_category(session, user.profile, category_id, payload)
    await session.commit()
    rows = await service.category_list(session)
    return next(row for row in rows if row.id == updated.id)


@router.delete(
    "/categories/{category_id}",
    response_model=CategoryDeleteOut,
    summary="Delete a category, refusing unless its contents have somewhere to go",
)
async def delete_category(
    user: AdminUserDep,
    session: SessionDep,
    category_id: CategoryId,
    reassign_to: Annotated[
        uuid.UUID | None, Query(description="Move its products and children here first")
    ] = None,
) -> CategoryDeleteOut:
    outcome, products, children = await service.delete_category(
        session, user.profile, category_id, reassign_to=reassign_to
    )
    await session.commit()
    message = (
        f"Deleted; {products} product(s) and {children} subcategory(ies) moved."
        if outcome == "moved"
        else "Category deleted."
    )
    return CategoryDeleteOut(
        id=category_id,
        outcome="moved" if outcome == "moved" else "deleted",
        products_moved=products,
        children_moved=children,
        message=message,
    )


@router.get("/brands", response_model=BrandListOut, summary="Every brand and its product count")
async def list_brands(_: AdminUserDep, session: SessionDep) -> BrandListOut:
    return BrandListOut(brands=await service.brand_list(session))


@router.post(
    "/brands",
    response_model=BrandAdminOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a brand",
)
async def create_brand(user: AdminUserDep, session: SessionDep, payload: BrandIn) -> BrandAdminOut:
    brand = await service.create_brand(session, user.profile, payload)
    await session.commit()
    rows = await service.brand_list(session)
    return next(row for row in rows if row.id == brand.id)


@router.patch("/brands/{brand_id}", response_model=BrandAdminOut, summary="Edit a brand")
async def update_brand(
    user: AdminUserDep, session: SessionDep, brand_id: BrandId, payload: BrandUpdateIn
) -> BrandAdminOut:
    brand = await service.update_brand(session, user.profile, brand_id, payload)
    await session.commit()
    rows = await service.brand_list(session)
    return next(row for row in rows if row.id == brand.id)


@router.delete(
    "/brands/{brand_id}",
    response_model=BrandDeleteOut,
    summary="Delete a brand that no product uses",
)
async def delete_brand(
    user: AdminUserDep, session: SessionDep, brand_id: BrandId
) -> BrandDeleteOut:
    await service.delete_brand(session, user.profile, brand_id)
    await session.commit()
    return BrandDeleteOut(id=brand_id, outcome="deleted", message="Brand deleted.")


@router.post(
    "/images",
    response_model=ImageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a product photo (validated, re-encoded, then stored)",
)
async def upload_image(
    _: AdminUserDep,
    file: Annotated[UploadFile, File(description="JPEG, PNG or WebP under 2 MB")],
) -> ImageOut:
    raw = await file.read(uploads.MAX_UPLOAD_BYTES + 1)
    if len(raw) > uploads.MAX_UPLOAD_BYTES:
        raise ValidationError(
            "Images must be under 2 MB.",
            code="image_too_large",
            details={"max_bytes": uploads.MAX_UPLOAD_BYTES},
        )
    return await uploads.upload_product_image(raw, filename=file.filename or "upload")
