# api/shopify_auth.py
# One-time Shopify OAuth handler.
# Visit http://148.230.120.176:8000/shopify/install once to get your access token.

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import config

router = APIRouter()

SCOPES = "read_products,write_products,read_orders,write_orders,read_inventory,write_inventory"
REDIRECT_URI = f"http://{148}.{230}.{120}.{176}:8000/shopify/callback"


@router.get("/shopify/install")
async def shopify_install():
    """
    Visit this URL to start the Shopify OAuth flow.
    It will redirect you to Shopify to authorize the app.
    """
    shop = "sp0t1s-41.myshopify.com"
    client_id = config.SHOPIFY_CLIENT_ID
    redirect_uri = f"http://148.230.120.176:8000/shopify/callback"

    auth_url = (
        f"https://{shop}/admin/oauth/authorize"
        f"?client_id={client_id}"
        f"&scope={SCOPES}"
        f"&redirect_uri={redirect_uri}"
    )
    return RedirectResponse(auth_url)


@router.get("/shopify/callback")
async def shopify_callback(request: Request):
    """
    Shopify redirects here after the merchant authorizes the app.
    Exchanges the code for a permanent access token.
    """
    code = request.query_params.get("code")
    shop = request.query_params.get("shop", "sp0t1s-41.myshopify.com")

    if not code:
        return HTMLResponse("<h1>Error: no code received from Shopify</h1>")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": config.SHOPIFY_CLIENT_ID,
                "client_secret": config.SHOPIFY_CLIENT_SECRET,
                "code": code,
            },
        )

    if res.status_code != 200:
        return HTMLResponse(f"<h1>Error getting token: {res.text}</h1>")

    data = res.json()
    token = data.get("access_token")

    if not token:
        return HTMLResponse(f"<h1>No token in response: {data}</h1>")

    return HTMLResponse(f"""
    <html>
    <body style="font-family:monospace;padding:40px;background:#111;color:#0f0">
    <h2 style="color:#0f0">✅ Shopify Connected!</h2>
    <p>Your access token:</p>
    <code style="background:#222;padding:10px;display:block;font-size:14px">{token}</code>
    <br>
    <p>Now run this on your VPS:</p>
    <code style="background:#222;padding:10px;display:block">
    sed -i 's/SHOPIFY_ACCESS_TOKEN=.*/SHOPIFY_ACCESS_TOKEN={token}/' ~/ecommerce-agent/backend/.env<br>
    /root/.hermes/node/bin/pm2 restart ecommerce-agent --update-env
    </code>
    </body>
    </html>
    """)
