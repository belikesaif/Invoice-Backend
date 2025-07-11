"""
Constants used in the document processing service.
"""

# Supported file types for invoices (async processing)
SUPPORTED_INVOICE_FILE_TYPES = {'pdf', 'png', 'jpg', 'jpeg'}

# Supported file types for general document processing
SUPPORTED_DOCUMENT_FILE_TYPES = ['pdf', 'jpg', 'jpeg', 'png']

# Default values - These might become less relevant with the universal prompt's strict extraction rules,
# but can be kept for other parts of the system or as fallback if parsing fails catastrophically.
DEFAULT_SUPPLIER_NAME = "Unknown"
DEFAULT_QUANTITY = 1.0
DEFAULT_PRICE = 0.0 # The prompt strongly advises against using 0 unless explicit.
DEFAULT_INVOICE_NUMBER = "Unknown" # This field is not in the new universal prompt's JSON output.

# Prompt for Gemini to extract structured data from an image of an invoice or contract
UNIVERSAL_SUPPLIER_ITEM_EXTRACTION_PROMPT = """
Extract the supplier name and all line items from the document.
The output MUST be a single valid JSON object. Do NOT include any text outside of the JSON object.
The JSON object should conform to the following schema:
{
    "supplier_name": "The full legal name of the primary supplier, vendor, or service provider. String or null if not identifiable.",
    "items": [
        // This MUST be a JSON array of item objects.
        // If no items/services are found, use an empty array: [].
        // Do NOT include a trailing comma after the last item object in this array.
        {
            "description": "The complete and exact name or description of the item, service, or product. CRITICAL: Normalize the description by removing excessive internal and surrounding spaces. Standardize common punctuation: ALL hyphens (-) used to connect words or parts of a description MUST NOT have adjacent spaces (e.g., 'Extra-Support-Module' NOT 'Extra - Support - Module'; 'Användarstöd-Agda' NOT 'Användarstöd - Agda'). Use slashes (/) without adjacent spaces (e.g., 'Web/Cloud' NOT 'Web / Cloud'). The description MUST NOT include quantity, units (e.g., 'st', 'pcs', 'ärende'), pricing, or totals; these belong in their respective fields. String.",
            "quantity": "The numerical quantity of the item. Default to 1.0 if not specified, unclear, or not applicable (e.g., for a general service or lump sum). Must be a Number.",
            "unit_price": "The numerical price per unit of the item or service. Extract the actual price value. NEVER use 0 unless the document explicitly states the price is zero. Must be a Number.",
            "total": "The total numerical price for this specific line item (quantity * unit_price). If explicitly stated, use that value. If not, it may be calculated or extracted if present. Must be a Number."
        }
        // ... more items if present
    ]
}

If a value is not found or cannot be determined, use `null` for string fields and ensure numeric fields are actual numbers or handle them appropriately if they must be omitted based on instructions (though the schema implies they are required or defaulted).
For "items", if the document contains no line items, services, or products, the value for "items" MUST be an empty array `[]`.
Ensure all monetary values are extracted as numbers (e.g., 123.45, not "123.45 USD").
The "description" for each item should be as complete and exact as possible, following the normalization rules above.
The "quantity" should be a number; if not specified or not applicable, default to 1.0.
The "unit_price" should be a number.
The "total" for each line item should be a number.
"""

# --- For testing purposes or specific extraction tasks ---
SPECIFIC_FIELDS_PROMPT = """
Please extract the following specific fields from the invoice image:
- Invoice ID
- Invoice Date
- Due Date
- Total Amount
- Supplier Name
- Client Name
Present the output as a JSON object.
"""

CONTRACT_ANALYSIS_PROMPT_DETAILED = """
Analyze the provided contract document image(s) and extract the following information.
This document may be in any language (English, Swedish, German, French, Spanish, etc.).
Please analyze the content regardless of the language and provide the response in English.

The output MUST be a single valid JSON object. Do NOT include any text outside of the JSON object.
{
  "contract_title": "The title of the contract, if available. String or null.",
  "effective_date": "The date the contract becomes effective (YYYY-MM-DD format). Date or null.",
  "expiration_date": "The date the contract expires (YYYY-MM-DD format). Date or null.",
  "supplier_name": "The full legal name of the supplier/vendor/service provider. String or null.",
  "client_name": "The full legal name of the client/customer. String or null.",
  "payment_terms": "Description of the payment terms (e.g., Net 30, upon receipt). String or null.",
  "renewal_terms": "Description of renewal terms, if any. String or null.",
  "termination_clause": "Summary of the termination clause, if present. String or null.",
  "scope_of_work_summary": "A brief summary of the scope of work or services to be provided. String or null.",
  "key_obligations_supplier": [
    "List of key obligations for the supplier. Array of strings or empty array []."
  ],
  "key_obligations_client": [
    "List of key obligations for the client. Array of strings or empty array []."
  ],
  "items": [
    {
      "description": "Description of the service, deliverable, or product mentioned in the contract. Translate to English if in another language. String.",
      "quantity": "Quantity or duration if specified. Default to 1.0 if not specified. Number.",
      "unit_price": "Price per unit/hour/service if specified. Number or null.",
      "total": "Total price for this item/service if specified. Number or null."
    }
    // ... more items if applicable
  ],
  "total_contract_value": "The total monetary value of the contract, if specified. Number or null.",
  "governing_law": "The jurisdiction whose laws govern the contract. String or null.",
  "confidentiality_clause": "Summary of the confidentiality clause, if present. String or null.",
  "indemnification_details": "Summary of indemnification provisions, if present. String or null.",
  "force_majeure_clause": "Summary of the force majeure clause, if present. String or null."
}

IMPORTANT MULTILINGUAL INSTRUCTIONS:
- This document may be in Swedish, German, French, Spanish, English, or other languages
- Read and understand the content in its original language
- Extract all information regardless of the source language
- Translate extracted text to English in the JSON response
- Pay special attention to:
  * Company names (leverantör, fournisseur, proveedor, Lieferant = supplier)
  * Service descriptions (tjänster, services, servicios, Dienstleistungen)
  * Dates (datum, date, fecha, Datum)
  * Monetary amounts (belopp, montant, cantidad, Betrag)
  * Contract terms (villkor, conditions, condiciones, Bedingungen)

If a value is not found or cannot be determined for a field, use `null`.
For dates, ensure YYYY-MM-DD format. If only month and year are found, use the first day of the month (e.g., YYYY-MM-01).
For arrays, if no relevant information is found, use an empty array `[]`.
Ensure the "items" array contains at least the main services or deliverables mentioned in the contract.
""" 