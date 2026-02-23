import httpx
import asyncio

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbl9zaXNjIiwicm9sZSI6IkFkbWluaXN0cmFkb3IgKE9ic2VydmF0b3JpbykiLCJleHAiOjE3NzE2Mzk3MjJ9.nCpUdONW83WBUrAJwSDLTt9Jx9iVqRbPVvU6Xv1MHXw"

async def main():
    async with httpx.AsyncClient() as client:
        # Request /ia/insights with auth header
        res = await client.get('http://localhost:8000/ia/insights', headers={'Authorization': f'Bearer {token}'})
        print(f"Status: {res.status_code}")
        print(f"Body: {res.text}")
        
        # Test me
        res2 = await client.get('http://localhost:8000/auth/me', headers={'Authorization': f'Bearer {token}'})
        print(f"Auth/Me Status: {res2.status_code}")
        print(f"Auth/Me Body: {res2.text}")
        

asyncio.run(main())
