import sys
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("Error: No se encontró pypdf ni PyPDF2")
        sys.exit(1)

def search_pdf(filename, search_term):
    try:
        reader = PdfReader(filename)
        found = False
        print(f"Buscando '{search_term}' en {filename}...\n")
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if search_term.lower() in text.lower():
                found = True
                print(f"--- Encontrado en Página {i + 1} ---")
                # Imprimir un contexto un poco más amplio si es posible, o toda la página
                print(text)
                print("\n" + "="*50 + "\n")
        
        if not found:
            print(f"No se encontró '{search_term}' en el documento.")

    except Exception as e:
        print(f"Error al leer el PDF: {e}")

if __name__ == "__main__":
    search_pdf("Documento Final PISCC-22 SEPTIEMBRE 2025.pdf", "habitantes")
