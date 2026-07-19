.PHONY: bootstrap format-check lint typecheck build test security-test verify clean
bootstrap:
	bash tools/bootstrap.sh
format-check:
	python -m ruff format --check api core tools tests domain_packs || true
lint:
	python -m ruff check api core tools tests domain_packs
typecheck:
	python -m mypy api core tools --ignore-missing-imports || true
build:
	python tools/generate_manifest.py --output artifacts/build-manifest.json
	cd frontend && npm run build || true
test:
	python -m pytest tests -q
security-test:
	python -m pytest tests/security -q
verify: format-check lint typecheck test build
clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache artifacts/build-manifest.json artifacts/electronics-research-pack.json
