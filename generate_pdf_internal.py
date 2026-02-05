import httpx
import asyncio

async def main():
    api_url = 'http://localhost:8000/reportes/generar-boletin'
    output_path = 'boletin_sisc.pdf'
    
    print(f"Generando boletín desde {api_url}...")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.get(api_url)
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"Boletín generado con éxito en: {output_path}")
            else:
                print(f"Error del servidor: {response.status_code}")
                print(response.text)
        except Exception as e:
            print(f"Error generando boletín: {e}")

if __name__ == "__main__":
    asyncio.run(main())
