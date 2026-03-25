"""
SAP O2C – Neo4j AuraDB Data Ingestion Script
=============================================
Reads all local JSONL files and ingests data into Neo4j AuraDB
via the official Python Bolt driver (no APOC file access needed).

Usage:
    1. pip install neo4j
    2. Set your AuraDB credentials below (or use environment variables)
    3. Run: python neo4j_ingest.py

The script runs each entity in order, prints progress, and is safe to
re-run (all writes use MERGE — idempotent).
"""

import json
import os
import glob
from neo4j import GraphDatabase

# ===========================================================================
# CONFIGURATION – Update these values
# ===========================================================================
NEO4J_URI      = os.getenv("NEO4J_URI",      "XXXXXXX")
NEO4J_USER     = os.getenv("NEO4J_USER",     "XXXXXXX")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "XXXXXXX")

# Path to the sap-o2c-data folder on your machine
DATA_DIR = os.path.join(os.path.dirname(__file__), "sap-o2c-data")

# Rows per transaction — increase for speed, decrease if AuraDB times out
BATCH_SIZE = 200

# ===========================================================================
# HELPERS
# ===========================================================================

def read_jsonl(folder: str):
    """Yield every JSON object across all JSONL files in a folder."""
    pattern = os.path.join(DATA_DIR, folder, "*.jsonl")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"  [!] No files found for: {folder}")
        return
    for path in files:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

def batch(iterable, size: int):
    """Split an iterable into chunks of `size`."""
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf

def flt(val):
    """Safe float conversion — returns None if empty/null."""
    try:
        return float(val) if val not in (None, "", "null") else None
    except (ValueError, TypeError):
        return None


def run_batched(session, cypher: str, folder: str, key: str = "rows"):
    """Read a JSONL folder and execute `cypher` in batches."""
    total = 0
    for chunk in batch(read_jsonl(folder), BATCH_SIZE):
        session.run(cypher, **{key: chunk})
        total += len(chunk)
    print(f"    [ok] {total:,} rows -> {folder}")


# ===========================================================================
# NODE INGESTION QUERIES
# ===========================================================================

Q_CUSTOMERS = """
UNWIND $rows AS r
MERGE (c:Customer {businessPartner: r.businessPartner})
SET c.customer             = r.customer,
    c.fullName             = r.businessPartnerFullName,
    c.name                 = r.businessPartnerName,
    c.category             = r.businessPartnerCategory,
    c.grouping             = r.businessPartnerGrouping,
    c.isBlocked            = r.businessPartnerIsBlocked,
    c.isMarkedForArchiving = r.isMarkedForArchiving,
    c.creationDate         = r.creationDate,
    c.lastChangeDate       = r.lastChangeDate
"""

Q_CUSTOMER_COMPANY = """
UNWIND $rows AS r
MATCH (c:Customer {businessPartner: r.customer})
SET c.companyCode           = r.companyCode,
    c.reconciliationAccount = r.reconciliationAccount,
    c.paymentTerms          = r.paymentTerms,
    c.customerAccountGroup  = r.customerAccountGroup
"""

Q_CUSTOMER_SALES = """
UNWIND $rows AS r
MATCH (c:Customer {businessPartner: r.customer})
SET c.salesOrganization       = r.salesOrganization,
    c.distributionChannel     = r.distributionChannel,
    c.currency                = r.currency,
    c.customerPaymentTerms    = r.customerPaymentTerms,
    c.shippingCondition       = r.shippingCondition,
    c.incotermsClassification = r.incotermsClassification,
    c.incotermsLocation1      = r.incotermsLocation1
"""

Q_ADDRESSES = """
UNWIND $rows AS r
MERGE (a:Address {addressId: r.addressId})
SET a.businessPartner   = r.businessPartner,
    a.cityName          = r.cityName,
    a.streetName        = r.streetName,
    a.postalCode        = r.postalCode,
    a.region            = r.region,
    a.country           = r.country,
    a.addressTimeZone   = r.addressTimeZone,
    a.validityStartDate = r.validityStartDate,
    a.validityEndDate   = r.validityEndDate
"""

Q_PLANTS = """
UNWIND $rows AS r
MERGE (pl:Plant {plant: r.plant})
SET pl.plantName           = r.plantName,
    pl.salesOrganization   = r.salesOrganization,
    pl.distributionChannel = r.distributionChannel,
    pl.division            = r.division,
    pl.factoryCalendar     = r.factoryCalendar,
    pl.addressId           = r.addressId,
    pl.language            = r.language
"""

Q_PRODUCTS = """
UNWIND $rows AS r
MERGE (pr:Product {product: r.product})
SET pr.productType         = r.productType,
    pr.productOldId        = r.productOldId,
    pr.baseUnit            = r.baseUnit,
    pr.grossWeight         = toFloat(coalesce(r.grossWeight, '0')),
    pr.netWeight           = toFloat(coalesce(r.netWeight,   '0')),
    pr.weightUnit          = r.weightUnit,
    pr.productGroup        = r.productGroup,
    pr.division            = r.division,
    pr.industrySector      = r.industrySector,
    pr.isMarkedForDeletion = r.isMarkedForDeletion,
    pr.creationDate        = r.creationDate,
    pr.lastChangeDate      = r.lastChangeDate
"""

Q_PRODUCT_DESC = """
UNWIND $rows AS r
MATCH (pr:Product {product: r.product})
WHERE r.language = 'EN'
SET pr.productDescription = r.productDescription
"""

Q_STORAGE_LOCATIONS = """
UNWIND $rows AS r
MERGE (sl:StorageLocation {storageLocationId: r.plant + '_' + r.storageLocation})
SET sl.plant           = r.plant,
    sl.storageLocation = r.storageLocation
"""

Q_SALES_ORDER_HEADERS = """
UNWIND $rows AS r
MERGE (so:SalesOrder {salesOrder: r.salesOrder})
SET so.salesOrderType             = r.salesOrderType,
    so.salesOrganization          = r.salesOrganization,
    so.distributionChannel        = r.distributionChannel,
    so.organizationDivision       = r.organizationDivision,
    so.soldToParty                = r.soldToParty,
    so.creationDate               = r.creationDate,
    so.createdByUser              = r.createdByUser,
    so.lastChangeDateTime         = r.lastChangeDateTime,
    so.totalNetAmount             = toFloat(coalesce(r.totalNetAmount, '0')),
    so.transactionCurrency        = r.transactionCurrency,
    so.overallDeliveryStatus      = r.overallDeliveryStatus,
    so.overallOrdReltdBillgStatus = r.overallOrdReltdBillgStatus,
    so.pricingDate                = r.pricingDate,
    so.requestedDeliveryDate      = r.requestedDeliveryDate,
    so.headerBillingBlockReason   = r.headerBillingBlockReason,
    so.deliveryBlockReason        = r.deliveryBlockReason,
    so.customerPaymentTerms       = r.customerPaymentTerms,
    so.incotermsClassification    = r.incotermsClassification,
    so.incotermsLocation1         = r.incotermsLocation1
"""

Q_SALES_ORDER_ITEMS = """
UNWIND $rows AS r
MERGE (si:SalesOrderItem {salesOrderItemId: r.salesOrder + '_' + r.salesOrderItem})
SET si.salesOrder              = r.salesOrder,
    si.salesOrderItem          = r.salesOrderItem,
    si.salesOrderItemCategory  = r.salesOrderItemCategory,
    si.material                = r.material,
    si.requestedQuantity       = toFloat(coalesce(r.requestedQuantity, '0')),
    si.requestedQuantityUnit   = r.requestedQuantityUnit,
    si.netAmount               = toFloat(coalesce(r.netAmount, '0')),
    si.transactionCurrency     = r.transactionCurrency,
    si.materialGroup           = r.materialGroup,
    si.productionPlant         = r.productionPlant,
    si.storageLocation         = r.storageLocation,
    si.salesDocumentRjcnReason = r.salesDocumentRjcnReason,
    si.itemBillingBlockReason  = r.itemBillingBlockReason
"""

Q_SCHEDULE_LINES = """
UNWIND $rows AS r
MERGE (sl:SalesOrderScheduleLine {
    scheduleLineId: r.salesOrder + '_' + r.salesOrderItem + '_' + r.scheduleLine
})
SET sl.salesOrder            = r.salesOrder,
    sl.salesOrderItem        = r.salesOrderItem,
    sl.scheduleLine          = r.scheduleLine,
    sl.confirmedDeliveryDate = r.confirmedDeliveryDate,
    sl.orderQuantityUnit     = r.orderQuantityUnit,
    sl.confirmedQty          = toFloat(coalesce(r.confdOrderQtyByMatlAvailCheck, '0'))
"""

Q_DELIVERY_HEADERS = """
UNWIND $rows AS r
MERGE (d:OutboundDelivery {deliveryDocument: r.deliveryDocument})
SET d.shippingPoint                = r.shippingPoint,
    d.creationDate                 = r.creationDate,
    d.actualGoodsMovementDate      = r.actualGoodsMovementDate,
    d.overallGoodsMovementStatus   = r.overallGoodsMovementStatus,
    d.overallPickingStatus         = r.overallPickingStatus,
    d.deliveryBlockReason          = r.deliveryBlockReason,
    d.headerBillingBlockReason     = r.headerBillingBlockReason,
    d.hdrGeneralIncompletionStatus = r.hdrGeneralIncompletionStatus
"""

Q_DELIVERY_ITEMS = """
UNWIND $rows AS r
MERGE (di:OutboundDeliveryItem {
    deliveryItemId: r.deliveryDocument + '_' + r.deliveryDocumentItem
})
SET di.deliveryDocument        = r.deliveryDocument,
    di.deliveryDocumentItem    = r.deliveryDocumentItem,
    di.actualDeliveryQuantity  = toFloat(coalesce(r.actualDeliveryQuantity, '0')),
    di.deliveryQuantityUnit    = r.deliveryQuantityUnit,
    di.plant                   = r.plant,
    di.storageLocation         = r.storageLocation,
    di.batch                   = r.batch,
    di.referenceSdDocument     = r.referenceSdDocument,
    di.referenceSdDocumentItem = r.referenceSdDocumentItem
"""

Q_BILLING_HEADERS = """
UNWIND $rows AS r
MERGE (b:BillingDocument {billingDocument: r.billingDocument})
SET b.billingDocumentType      = r.billingDocumentType,
    b.billingDocumentDate      = r.billingDocumentDate,
    b.creationDate             = r.creationDate,
    b.lastChangeDateTime       = r.lastChangeDateTime,
    b.totalNetAmount           = toFloat(coalesce(r.totalNetAmount, '0')),
    b.transactionCurrency      = r.transactionCurrency,
    b.companyCode              = r.companyCode,
    b.fiscalYear               = r.fiscalYear,
    b.accountingDocument       = r.accountingDocument,
    b.soldToParty              = r.soldToParty,
    b.isCancelled              = r.billingDocumentIsCancelled,
    b.cancelledBillingDocument = r.cancelledBillingDocument
"""

Q_BILLING_ITEMS = """
UNWIND $rows AS r
MERGE (bi:BillingDocumentItem {
    billingItemId: r.billingDocument + '_' + r.billingDocumentItem
})
SET bi.billingDocument       = r.billingDocument,
    bi.billingDocumentItem   = r.billingDocumentItem,
    bi.material              = r.material,
    bi.billingQuantity       = toFloat(coalesce(r.billingQuantity, '0')),
    bi.billingQuantityUnit   = r.billingQuantityUnit,
    bi.netAmount             = toFloat(coalesce(r.netAmount, '0')),
    bi.transactionCurrency   = r.transactionCurrency,
    bi.referenceSdDocument   = r.referenceSdDocument,
    bi.referenceSdDocumentItem = r.referenceSdDocumentItem
"""

Q_JOURNAL_ENTRIES = """
UNWIND $rows AS r
MERGE (j:JournalEntry {
    accountingDocumentId: r.companyCode + '_' + r.fiscalYear + '_'
                        + r.accountingDocument + '_' + r.accountingDocumentItem
})
SET j.accountingDocument          = r.accountingDocument,
    j.accountingDocumentItem       = r.accountingDocumentItem,
    j.companyCode                  = r.companyCode,
    j.fiscalYear                   = r.fiscalYear,
    j.glAccount                    = r.glAccount,
    j.referenceDocument            = r.referenceDocument,
    j.customer                     = r.customer,
    j.amountInTransactionCurrency  = toFloat(coalesce(r.amountInTransactionCurrency, '0')),
    j.transactionCurrency          = r.transactionCurrency,
    j.postingDate                  = r.postingDate,
    j.documentDate                 = r.documentDate,
    j.accountingDocumentType       = r.accountingDocumentType,
    j.profitCenter                 = r.profitCenter,
    j.financialAccountType         = r.financialAccountType,
    j.clearingDate                 = r.clearingDate,
    j.clearingAccountingDocument   = r.clearingAccountingDocument
"""

Q_PAYMENTS = """
UNWIND $rows AS r
WITH r WHERE r.clearingAccountingDocument IS NOT NULL
MERGE (p:Payment {
    paymentId: r.companyCode + '_' + r.fiscalYear + '_' + r.clearingAccountingDocument
})
SET p.accountingDocument          = r.accountingDocument,
    p.clearingAccountingDocument  = r.clearingAccountingDocument,
    p.companyCode                 = r.companyCode,
    p.fiscalYear                  = r.fiscalYear,
    p.customer                    = r.customer,
    p.amountInTransactionCurrency = toFloat(coalesce(r.amountInTransactionCurrency, '0')),
    p.transactionCurrency         = r.transactionCurrency,
    p.clearingDate                = r.clearingDate,
    p.postingDate                 = r.postingDate,
    p.glAccount                   = r.glAccount
"""


# ===========================================================================
# RELATIONSHIP QUERIES
# ===========================================================================

RELATIONSHIPS = [
    ("Customer -> Address",
     "MATCH (c:Customer), (a:Address) WHERE a.businessPartner = c.businessPartner MERGE (c)-[:HAS_ADDRESS]->(a)"),

    ("Customer -> SalesOrder",
     "MATCH (c:Customer), (so:SalesOrder) WHERE so.soldToParty = c.businessPartner MERGE (c)-[:PLACED]->(so)"),

    ("SalesOrder -> SalesOrderItem",
     "MATCH (so:SalesOrder), (si:SalesOrderItem) WHERE si.salesOrder = so.salesOrder MERGE (so)-[:HAS_ITEM]->(si)"),

    ("SalesOrderItem -> Product",
     "MATCH (si:SalesOrderItem), (pr:Product) WHERE si.material = pr.product MERGE (si)-[:REFERENCES]->(pr)"),

    ("SalesOrderItem -> Plant",
     "MATCH (si:SalesOrderItem), (pl:Plant) WHERE si.productionPlant = pl.plant MERGE (si)-[:PRODUCED_AT]->(pl)"),

    ("SalesOrderItem -> ScheduleLine",
     """MATCH (si:SalesOrderItem), (sl:SalesOrderScheduleLine)
        WHERE sl.salesOrder = si.salesOrder AND sl.salesOrderItem = si.salesOrderItem
        MERGE (si)-[:HAS_SCHEDULE_LINE]->(sl)"""),

    ("OutboundDelivery -> DeliveryItem",
     """MATCH (d:OutboundDelivery), (di:OutboundDeliveryItem)
        WHERE di.deliveryDocument = d.deliveryDocument
        MERGE (d)-[:HAS_DELIVERY_ITEM]->(di)"""),

    ("OutboundDeliveryItem -> SalesOrderItem (FULFILLS)",
     """MATCH (di:OutboundDeliveryItem), (si:SalesOrderItem)
        WHERE di.referenceSdDocument = si.salesOrder
          AND toInteger(di.referenceSdDocumentItem) = toInteger(si.salesOrderItem)
        MERGE (di)-[:FULFILLS]->(si)"""),

    ("OutboundDeliveryItem -> Plant",
     "MATCH (di:OutboundDeliveryItem), (pl:Plant) WHERE di.plant = pl.plant MERGE (di)-[:SHIPPED_FROM]->(pl)"),

    ("OutboundDeliveryItem -> StorageLocation",
     """MATCH (di:OutboundDeliveryItem), (sl:StorageLocation)
        WHERE sl.plant = di.plant AND sl.storageLocation = di.storageLocation
        MERGE (di)-[:STORED_AT]->(sl)"""),

    ("BillingDocument -> Customer",
     "MATCH (b:BillingDocument), (c:Customer) WHERE b.soldToParty = c.businessPartner MERGE (b)-[:BILLED_TO]->(c)"),

    ("BillingDocument -> BillingDocumentItem",
     """MATCH (b:BillingDocument), (bi:BillingDocumentItem)
        WHERE bi.billingDocument = b.billingDocument
        MERGE (b)-[:HAS_BILLING_ITEM]->(bi)"""),

    ("BillingDocumentItem -> Product",
     "MATCH (bi:BillingDocumentItem), (pr:Product) WHERE bi.material = pr.product MERGE (bi)-[:BILLS_MATERIAL]->(pr)"),

    ("BillingDocumentItem -> OutboundDelivery",
     """MATCH (bi:BillingDocumentItem), (d:OutboundDelivery)
        WHERE bi.referenceSdDocument = d.deliveryDocument
        MERGE (bi)-[:REFERENCES_DELIVERY]->(d)"""),

    ("BillingDocument -> JournalEntry",
     """MATCH (b:BillingDocument), (j:JournalEntry)
        WHERE j.referenceDocument = b.billingDocument
        MERGE (b)-[:GENERATES]->(j)"""),

    ("JournalEntry -> Payment",
     """MATCH (j:JournalEntry), (p:Payment)
        WHERE j.clearingAccountingDocument = p.clearingAccountingDocument
          AND j.companyCode = p.companyCode
        MERGE (j)-[:CLEARED_BY]->(p)"""),

    ("Customer -> Payment",
     "MATCH (c:Customer), (p:Payment) WHERE p.customer = c.businessPartner MERGE (c)-[:PAID]->(p)"),

    ("Plant -> StorageLocation",
     "MATCH (pl:Plant), (sl:StorageLocation) WHERE sl.plant = pl.plant MERGE (pl)-[:HAS_STORAGE_LOCATION]->(sl)"),
]

Q_PRODUCT_PLANT_RELS = """
UNWIND $rows AS r
MATCH (pr:Product {product: r.product})
MATCH (pl:Plant   {plant:   r.plant})
MERGE (pr)-[rel:STOCKED_AT]->(pl)
SET rel.profitCenter          = r.profitCenter,
    rel.mrpType               = r.mrpType,
    rel.availabilityCheckType = r.availabilityCheckType
"""


# ===========================================================================
# MAIN
# ===========================================================================

def main():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    print(f"\nConnected to: {NEO4J_URI}\n")

    with driver.session() as session:

        # ── NODES ──────────────────────────────────────────────────────────
        print("=== Loading Nodes ===")

        print("  Customers...")
        run_batched(session, Q_CUSTOMERS,       "business_partners")
        run_batched(session, Q_CUSTOMER_COMPANY,"customer_company_assignments")
        run_batched(session, Q_CUSTOMER_SALES,  "customer_sales_area_assignments")

        print("  Addresses...")
        run_batched(session, Q_ADDRESSES, "business_partner_addresses")

        print("  Plants...")
        run_batched(session, Q_PLANTS, "plants")

        print("  Products...")
        run_batched(session, Q_PRODUCTS,      "products")
        run_batched(session, Q_PRODUCT_DESC,  "product_descriptions")

        print("  Storage Locations...")
        run_batched(session, Q_STORAGE_LOCATIONS, "product_storage_locations")

        print("  Sales Orders...")
        run_batched(session, Q_SALES_ORDER_HEADERS, "sales_order_headers")
        run_batched(session, Q_SALES_ORDER_ITEMS,   "sales_order_items")
        run_batched(session, Q_SCHEDULE_LINES,       "sales_order_schedule_lines")

        print("  Deliveries...")
        run_batched(session, Q_DELIVERY_HEADERS, "outbound_delivery_headers")
        run_batched(session, Q_DELIVERY_ITEMS,   "outbound_delivery_items")

        print("  Billing...")
        run_batched(session, Q_BILLING_HEADERS, "billing_document_headers")
        run_batched(session, Q_BILLING_HEADERS, "billing_document_cancellations")  # updates isCancelled
        run_batched(session, Q_BILLING_ITEMS,   "billing_document_items")

        print("  Journal Entries...")
        run_batched(session, Q_JOURNAL_ENTRIES, "journal_entry_items_accounts_receivable")

        print("  Payments...")
        run_batched(session, Q_PAYMENTS, "payments_accounts_receivable")

        # ── RELATIONSHIPS ──────────────────────────────────────────────────
        print("\n=== Creating Relationships ===")

        for label, cypher in RELATIONSHIPS:
            result = session.run(cypher)
            summary = result.consume()
            print(f"    [ok] {label} "
                  f"({summary.counters.relationships_created:,} created)")

        print("  Product -> Plant (STOCKED_AT)...")
        run_batched(session, Q_PRODUCT_PLANT_RELS, "product_plants")

        # ── FLOW SHORTCUTS ─────────────────────────────────────────────────
        print("\n=== Creating Flow Shortcuts ===")

        session.run("""
            MATCH (so:SalesOrder)-[:HAS_ITEM]->(:SalesOrderItem)
                  <-[:FULFILLS]-(di:OutboundDeliveryItem)
                  <-[:HAS_DELIVERY_ITEM]-(d:OutboundDelivery)
            WITH DISTINCT so, d
            MERGE (so)-[:DELIVERED_VIA]->(d)
        """)
        print("    [ok] SalesOrder -[:DELIVERED_VIA]-> OutboundDelivery")

        session.run("""
            MATCH (d:OutboundDelivery)<-[:REFERENCES_DELIVERY]-(:BillingDocumentItem)
                  <-[:HAS_BILLING_ITEM]-(b:BillingDocument)
            WITH DISTINCT d, b
            MERGE (d)-[:BILLED_AS]->(b)
        """)
        print("    [ok] OutboundDelivery -[:BILLED_AS]-> BillingDocument")

        # ── STATUS LABELS ──────────────────────────────────────────────────
        print("\n=== Applying Status Labels ===")

        status_queries = [
            ("BillingDocument: ActiveBilling",
             "MATCH (b:BillingDocument) WHERE b.isCancelled = false "
             "CALL apoc.create.addLabels(b, ['ActiveBilling']) YIELD node RETURN count(node)"),
            ("BillingDocument: CancelledBilling",
             "MATCH (b:BillingDocument) WHERE b.isCancelled = true "
             "CALL apoc.create.addLabels(b, ['CancelledBilling']) YIELD node RETURN count(node)"),
            ("SalesOrder: PendingDelivery",
             "MATCH (so:SalesOrder) WHERE so.overallDeliveryStatus IN ['A',''] OR so.overallDeliveryStatus IS NULL "
             "CALL apoc.create.addLabels(so, ['PendingDelivery']) YIELD node RETURN count(node)"),
            ("SalesOrder: PartiallyDelivered",
             "MATCH (so:SalesOrder) WHERE so.overallDeliveryStatus = 'B' "
             "CALL apoc.create.addLabels(so, ['PartiallyDelivered']) YIELD node RETURN count(node)"),
            ("SalesOrder: FullyDelivered",
             "MATCH (so:SalesOrder) WHERE so.overallDeliveryStatus = 'C' "
             "CALL apoc.create.addLabels(so, ['FullyDelivered']) YIELD node RETURN count(node)"),
            ("OutboundDelivery: GoodsMovementPending",
             "MATCH (d:OutboundDelivery) WHERE d.overallGoodsMovementStatus = 'A' "
             "CALL apoc.create.addLabels(d, ['GoodsMovementPending']) YIELD node RETURN count(node)"),
            ("OutboundDelivery: GoodsMovementComplete",
             "MATCH (d:OutboundDelivery) WHERE d.overallGoodsMovementStatus = 'C' "
             "CALL apoc.create.addLabels(d, ['GoodsMovementComplete']) YIELD node RETURN count(node)"),
        ]

        for label, cypher in status_queries:
            result = session.run(cypher)
            count = result.single()[0]
            print(f"    [ok] {label} -- {count:,} nodes labelled")

        # ── VERIFICATION ───────────────────────────────────────────────────
        print("\n=== Node Counts ===")
        result = session.run(
            "MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count "
            "ORDER BY count DESC"
        )
        for record in result:
            print(f"    {record['label']:<30} {record['count']:>8,}")

    driver.close()
    print("\n[DONE] Ingestion complete!\n")


if __name__ == "__main__":
    main()
