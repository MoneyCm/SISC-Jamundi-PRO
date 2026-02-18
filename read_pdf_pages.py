import sys
try:
    from pypdf import PdfReader
except ImportError:
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        print("Error: No se encontró pypdf ni PyPDF2")
        sys.exit(1)

def read_pdf_pages(filename, pages):
    try:
        reader = PdfReader(filename)
        for page_num in pages:
            if 0 <= page_num < len(reader.pages):
                page = reader.pages[page_num]
                text = page.extract_text()
                print(f"\n--- Página {page_num + 1} ---\n")
                print(text)
            else:
                print(f"Página {page_num + 1} fuera de rango.")
    except Exception as e:
        print(f"Error al leer el PDF: {e}")

if __name__ == "__main__":
    # Pagina 24 (indice 23)
    read_pdf_pages("Documento Final PISCC-22 SEPTIEMBRE 2025.pdf", [23]) 
