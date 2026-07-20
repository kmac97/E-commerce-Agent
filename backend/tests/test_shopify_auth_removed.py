# Regression check: the insecure Shopify OAuth route must stay gone.
# No pytest/fastapi available in this environment, so this is a plain,
# dependency-free script — run with `python backend/tests/test_shopify_auth_removed.py`.

import pathlib

BACKEND = pathlib.Path(__file__).resolve().parent.parent


def test_shopify_auth_file_deleted():
    assert not (BACKEND / "api" / "shopify_auth.py").exists(), (
        "backend/api/shopify_auth.py exists again — it exposed the live Shopify "
        "access token in a plaintext HTTP response and must stay removed."
    )


def test_main_does_not_register_shopify_auth_router():
    main_src = (BACKEND / "main.py").read_text(encoding="utf-8")
    assert "shopify_auth" not in main_src, (
        "main.py references shopify_auth again — the insecure OAuth route "
        "must not be re-registered."
    )


if __name__ == "__main__":
    test_shopify_auth_file_deleted()
    test_main_does_not_register_shopify_auth_router()
    print("OK — shopify_auth route stays removed")
