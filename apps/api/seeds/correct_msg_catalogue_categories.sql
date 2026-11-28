-- Correct the initial live MSG import in one atomic statement. Products move to existing
-- top-level roots, source child labels remain in descriptions for search, and the
-- now-unused import-only taxonomy is removed. Guards make this one-time operation safe.
DO $msg_correction$
DECLARE
  n_products integer; n_imported_refs integer; n_roots integer; n_children integer; n_targets integer;
  n_updated integer; n_good integer; n_bad_desc integer; n_deleted integer;
BEGIN
  SELECT count(*) INTO n_products FROM public.products p JOIN public.brands b ON b.id=p.brand_id WHERE b.slug='msg';
  SELECT count(*) INTO n_imported_refs FROM public.products p JOIN public.brands b ON b.id=p.brand_id
    JOIN public.categories c ON c.id=p.category_id WHERE b.slug='msg' AND c.slug LIKE 'msg-import-%';
  SELECT count(*) INTO n_roots FROM public.categories WHERE slug LIKE 'msg-import-%' AND parent_id IS NULL;
  SELECT count(*) INTO n_children FROM public.categories WHERE slug LIKE 'msg-import-%' AND parent_id IS NOT NULL;
  SELECT count(*) INTO n_targets FROM public.categories WHERE parent_id IS NULL AND slug IN
    ('atta-rice-pantry','ayurvedic-herbs','beauty-personal-care','beverages','edible-oils-ghee',
     'pulses-dals','snacks-biscuits','soaps-detergents','spices-masale');
  IF n_products <> 190 OR n_imported_refs <> 190 OR n_roots <> 6 OR n_children <> 39 OR n_targets <> 9 THEN
    RAISE EXCEPTION 'MSG preflight mismatch: products %, imported refs %, roots %, children %, targets %',
      n_products,n_imported_refs,n_roots,n_children,n_targets;
  END IF;

  UPDATE public.products p
  SET category_id = target.id,
      description = CASE WHEN source_category.parent_id IS NULL THEN ''
        ELSE 'MSG supplier category: ' || source_category.name END
  FROM public.categories source_category
  LEFT JOIN public.categories source_parent ON source_parent.id=source_category.parent_id
  JOIN public.brands brand ON brand.slug='msg'
  JOIN public.categories target ON target.slug = CASE coalesce(source_parent.slug, source_category.slug)
    WHEN 'msg-import-grocery' THEN CASE source_category.name
      WHEN 'Pulses' THEN 'pulses-dals'
      WHEN 'Spices & Herbs' THEN 'spices-masale'
      WHEN 'Tea' THEN 'beverages'
      ELSE 'atta-rice-pantry' END
    WHEN 'msg-import-health-care' THEN 'ayurvedic-herbs'
    WHEN 'msg-import-home-body-care' THEN CASE source_category.name
      WHEN 'Tooth Brush' THEN 'beauty-personal-care'
      ELSE 'soaps-detergents' END
    WHEN 'msg-import-confectionery' THEN CASE source_category.name
      WHEN 'Sharbat' THEN 'beverages'
      ELSE 'snacks-biscuits' END
    WHEN 'msg-import-cosmetics' THEN 'beauty-personal-care'
    WHEN 'msg-import-edible-oil-ghee' THEN 'edible-oils-ghee'
  END AND target.parent_id IS NULL
  WHERE p.brand_id=brand.id AND p.category_id=source_category.id
    AND source_category.slug LIKE 'msg-import-%';
  GET DIAGNOSTICS n_updated = ROW_COUNT;
  IF n_updated <> 190 THEN RAISE EXCEPTION 'Expected 190 MSG products updated, got %', n_updated; END IF;

  SELECT count(*) INTO n_good FROM public.products p JOIN public.brands b ON b.id=p.brand_id
    JOIN public.categories c ON c.id=p.category_id
    WHERE b.slug='msg' AND c.parent_id IS NULL AND c.slug IN
      ('atta-rice-pantry','ayurvedic-herbs','beauty-personal-care','beverages','edible-oils-ghee',
       'pulses-dals','snacks-biscuits','soaps-detergents','spices-masale');
  SELECT count(*) INTO n_bad_desc FROM public.products p JOIN public.brands b ON b.id=p.brand_id
    WHERE b.slug='msg' AND coalesce(p.description,'') <> '' AND p.description NOT LIKE 'MSG supplier category:%';
  IF n_good <> 190 OR n_bad_desc <> 0 THEN
    RAISE EXCEPTION 'MSG verification failed: parent-category products %, unexpected descriptions %', n_good,n_bad_desc;
  END IF;

  DELETE FROM public.categories WHERE slug LIKE 'msg-import-%' AND parent_id IS NOT NULL;
  GET DIAGNOSTICS n_deleted = ROW_COUNT;
  IF n_deleted <> 39 THEN RAISE EXCEPTION 'Expected 39 imported child categories deleted, got %', n_deleted; END IF;
  DELETE FROM public.categories WHERE slug LIKE 'msg-import-%' AND parent_id IS NULL;
  GET DIAGNOSTICS n_deleted = ROW_COUNT;
  IF n_deleted <> 6 THEN RAISE EXCEPTION 'Expected 6 imported parent categories deleted, got %', n_deleted; END IF;
END;
$msg_correction$;
