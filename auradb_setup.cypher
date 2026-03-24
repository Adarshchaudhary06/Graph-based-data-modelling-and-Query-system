// =============================================================================
// SAP O2C – AuraDB Browser Console Setup
// =============================================================================
// Paste each block below into the Neo4j AuraDB Browser console and run.
// These are pure Cypher statements — no plugins or file access required.
// Run STEP 1 first, then run the Python ingest script, then STEP 2.
// =============================================================================


// ===========================================================================
// STEP 1 – CONSTRAINTS & INDEXES
// Run this BEFORE loading any data.
// ===========================================================================

CREATE CONSTRAINT customer_pk IF NOT EXISTS
  FOR (c:Customer) REQUIRE c.businessPartner IS UNIQUE;

CREATE CONSTRAINT address_pk IF NOT EXISTS
  FOR (a:Address) REQUIRE a.addressId IS UNIQUE;

CREATE CONSTRAINT sales_order_pk IF NOT EXISTS
  FOR (s:SalesOrder) REQUIRE s.salesOrder IS UNIQUE;

CREATE CONSTRAINT sales_order_item_pk IF NOT EXISTS
  FOR (si:SalesOrderItem) REQUIRE si.salesOrderItemId IS UNIQUE;

CREATE CONSTRAINT schedule_line_pk IF NOT EXISTS
  FOR (sl:SalesOrderScheduleLine) REQUIRE sl.scheduleLineId IS UNIQUE;

CREATE CONSTRAINT delivery_pk IF NOT EXISTS
  FOR (d:OutboundDelivery) REQUIRE d.deliveryDocument IS UNIQUE;

CREATE CONSTRAINT delivery_item_pk IF NOT EXISTS
  FOR (di:OutboundDeliveryItem) REQUIRE di.deliveryItemId IS UNIQUE;

CREATE CONSTRAINT billing_doc_pk IF NOT EXISTS
  FOR (b:BillingDocument) REQUIRE b.billingDocument IS UNIQUE;

CREATE CONSTRAINT billing_item_pk IF NOT EXISTS
  FOR (bi:BillingDocumentItem) REQUIRE bi.billingItemId IS UNIQUE;

CREATE CONSTRAINT journal_entry_pk IF NOT EXISTS
  FOR (j:JournalEntry) REQUIRE j.accountingDocumentId IS UNIQUE;

CREATE CONSTRAINT payment_pk IF NOT EXISTS
  FOR (p:Payment) REQUIRE p.paymentId IS UNIQUE;

CREATE CONSTRAINT product_pk IF NOT EXISTS
  FOR (pr:Product) REQUIRE pr.product IS UNIQUE;

CREATE CONSTRAINT plant_pk IF NOT EXISTS
  FOR (pl:Plant) REQUIRE pl.plant IS UNIQUE;

CREATE CONSTRAINT storage_location_pk IF NOT EXISTS
  FOR (sl:StorageLocation) REQUIRE sl.storageLocationId IS UNIQUE;

// Performance indexes
CREATE INDEX billing_soldto       IF NOT EXISTS FOR (b:BillingDocument)      ON (b.soldToParty);
CREATE INDEX billing_accounting   IF NOT EXISTS FOR (b:BillingDocument)      ON (b.accountingDocument);
CREATE INDEX journal_reference    IF NOT EXISTS FOR (j:JournalEntry)         ON (j.referenceDocument);
CREATE INDEX journal_clearing     IF NOT EXISTS FOR (j:JournalEntry)         ON (j.clearingAccountingDocument);
CREATE INDEX so_sold_to           IF NOT EXISTS FOR (s:SalesOrder)           ON (s.soldToParty);
CREATE INDEX delivery_item_ref    IF NOT EXISTS FOR (di:OutboundDeliveryItem) ON (di.referenceSdDocument);
CREATE INDEX billing_item_ref     IF NOT EXISTS FOR (bi:BillingDocumentItem)  ON (bi.referenceSdDocument);


// ===========================================================================
// STEP 2 – FLOW SHORTCUTS  (run AFTER the Python ingest script completes)
// These create header-level O2C shortcuts: SalesOrder→Delivery→Billing
// ===========================================================================

// SalesOrder → OutboundDelivery  (3-hop shortcut)
MATCH (so:SalesOrder)-[:HAS_ITEM]->(:SalesOrderItem)
      <-[:FULFILLS]-(di:OutboundDeliveryItem)
      <-[:HAS_DELIVERY_ITEM]-(d:OutboundDelivery)
WITH DISTINCT so, d
MERGE (so)-[:DELIVERED_VIA]->(d);

// OutboundDelivery → BillingDocument  (3-hop shortcut)
MATCH (d:OutboundDelivery)<-[:REFERENCES_DELIVERY]-(:BillingDocumentItem)
      <-[:HAS_BILLING_ITEM]-(b:BillingDocument)
WITH DISTINCT d, b
MERGE (d)-[:BILLED_AS]->(b);


// ===========================================================================
// STEP 3 – STATUS LABELS  (run AFTER the Python ingest script completes)
// Uses native SET n:Label syntax — no APOC required (Neo4j 5+ / AuraDB)
// ===========================================================================

// BillingDocument status
MATCH (b:BillingDocument) WHERE b.isCancelled = false
SET b:ActiveBilling
RETURN count(b) AS activeBillingLabelled;

MATCH (b:BillingDocument) WHERE b.isCancelled = true
SET b:CancelledBilling
RETURN count(b) AS cancelledBillingLabelled;

// SalesOrder delivery status
MATCH (so:SalesOrder)
WHERE so.overallDeliveryStatus IN ['A', ''] OR so.overallDeliveryStatus IS NULL
SET so:PendingDelivery
RETURN count(so) AS pendingDeliveryLabelled;

MATCH (so:SalesOrder) WHERE so.overallDeliveryStatus = 'B'
SET so:PartiallyDelivered
RETURN count(so) AS partiallyDeliveredLabelled;

MATCH (so:SalesOrder) WHERE so.overallDeliveryStatus = 'C'
SET so:FullyDelivered
RETURN count(so) AS fullyDeliveredLabelled;

// OutboundDelivery goods movement status
MATCH (d:OutboundDelivery) WHERE d.overallGoodsMovementStatus = 'A'
SET d:GoodsMovementPending
RETURN count(d) AS goodsMovementPendingLabelled;

MATCH (d:OutboundDelivery) WHERE d.overallGoodsMovementStatus = 'C'
SET d:GoodsMovementComplete
RETURN count(d) AS goodsMovementCompleteLabelled;



// ===========================================================================
// VERIFICATION – Run after everything to confirm node counts
// ===========================================================================

MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC;
