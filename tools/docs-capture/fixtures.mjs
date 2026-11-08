/**
 * Fixture data for the user guide.
 *
 * The dataset is Chinook 1.4.5, vendored under `fixtures/chinook/` (MIT, see the
 * LICENSE there). Everything the guide shows comes from that one database:
 * CSV exports for the Files screen, the SQLite connection for Data Sources,
 * and notebooks built from real aggregates.
 *
 * Files whose content is generated at seed time declare an `sql` query; the
 * others carry `content` directly.
 */
import {
   chartDocument,
   chartsGalleryNotebook,
   dataTableDocument,
   featureTourNotebook,
   FIXTURE_EPOCH,
   pythonExecutionNotebook,
   pythonWorkflowNotebook,
   revenueNotebook
} from "./fixtures/notebooks.mjs";

export { FIXTURE_EPOCH };

export const FIXTURE_PROJECT_CODE = "local";

export const catalogFixture = {
   displayName: "Chinook music store",
   description: "Chinook sample database (MIT), a digital music store.",
   providerKind: "sqlite_external",
   connectionKind: "external",
   sourceCategory: "sql",
   authType: "none",
   executionMode: "duckdb_federated",
   defaultNamespace: "main",
   databaseFile: "chinook.db",
   sqlFile: "chinook/Chinook_Sqlite.sql"
};


const CONCEPT_VERIFIED_AT = "2026-02-16T09:00:00Z";

export const knowledgeConcepts = [
   {
      id: "metrics/revenue",
      type: "Metric",
      title: "Revenue",
      description:
         "Total money billed to customers, summed from invoice totals.",
      tags: ["finance", "chinook"],
      status: "stable",
      body:
         "Revenue is `SUM(Invoice.Total)` over all invoices. Invoice totals reconcile with " +
         "`SUM(InvoiceLine.UnitPrice * InvoiceLine.Quantity)`, so either path returns the same " +
         "number for the Chinook sample store. Report revenue by `Invoice.BillingCountry` when " +
         "the question is about markets, and by `Invoice.InvoiceDate` when the question is about trend.",
      attestation: {
         generated: { by: "human:raymond", at: CONCEPT_VERIFIED_AT },
         verified: [{ by: "human:raymond", at: CONCEPT_VERIFIED_AT }]
      }
   },
   {
      id: "entities/customer",
      type: "Entity",
      title: "Customer",
      description:
         "A person or company that buys tracks; invoices and support reps hang off it.",
      tags: ["chinook", "entity"],
      status: "stable",
      body:
         "`Customer` has one row per buyer. `Customer.Country` is the customer's home country, " +
         "while `Invoice.BillingCountry` is where the invoice was billed; the sample data has no " +
         "cases where the two differ. `Customer.SupportRepId` points at `Employee`.",
      attestation: {
         verified: [{ by: "human:raymond", at: CONCEPT_VERIFIED_AT }]
      }
   },
   {
      id: "joins/invoice-customer",
      type: "Join",
      title: "Invoice to Customer",
      description:
         "How to attach buyer attributes to revenue without duplicating invoice lines.",
      tags: ["chinook", "join"],
      status: "draft",
      body:
         "Join `Invoice.CustomerId` to `Customer.CustomerId`. Aggregate at the invoice level " +
         "before joining when the measure is `Invoice.Total`; aggregating `InvoiceLine` first " +
         "avoids multiplying rows when a customer has several invoices.",
      attestation: {
         generated: { by: "human:raymond", at: CONCEPT_VERIFIED_AT }
      }
   }
];

export const catalogEntities = [
   "Album",
   "Artist",
   "Customer",
   "Employee",
   "Genre",
   "Invoice",
   "InvoiceLine",
   "MediaType",
   "Playlist",
   "PlaylistTrack",
   "Track"
];

const handbook = `# Music store handbook

## About the store

Chinook is a digital music store. Customers buy individual tracks, and every
purchase creates an invoice with one or more invoice lines.

## Reporting rules

- Revenue is \`InvoiceLine.UnitPrice * InvoiceLine.Quantity\`.
- Country comes from the customer's billing country on the invoice.
- A "track sold" is the sum of invoice-line quantities, not the number of rows.

## Open questions

1. Which genres grow fastest outside North America?
2. Do larger invoices come from repeat customers?
`;

export const seedFiles = [
   {
      name: "customers.csv",
      contentType: "text/csv",
      sql: "select CustomerId, FirstName, LastName, City, Country from Customer order by CustomerId limit 12"
   },
   {
      name: "invoices.csv",
      contentType: "text/csv",
      sql: "select InvoiceId, CustomerId, InvoiceDate, BillingCountry, Total from Invoice order by InvoiceId desc limit 12"
   },
   {
      name: "invoice-lines.csv",
      contentType: "text/csv",
      sql: "select InvoiceLineId, InvoiceId, TrackId, UnitPrice, Quantity from InvoiceLine order by InvoiceLineId desc limit 20"
   },
   {
      name: "music-store-handbook.md",
      contentType: "text/markdown",
      content: handbook
   },
   {
      name: "notebook-block-types.kontext",
      contentType: "application/json",
      content: `${JSON.stringify(featureTourNotebook, null, 3)}\n`
   },
   {
      name: "chart-gallery.kontext",
      contentType: "application/json",
      content: `${JSON.stringify(chartsGalleryNotebook, null, 3)}\n`
   },
   {
      name: "sql-and-python.kontext",
      contentType: "application/json",
      content: `${JSON.stringify(pythonWorkflowNotebook, null, 3)}\n`
   },
   {
      name: "python-execution.kontext",
      contentType: "application/json",
      content: `${JSON.stringify(pythonExecutionNotebook, null, 3)}\n`
   },
   {
      name: "revenue-notebook.kontext",
      contentType: "application/json",
      content: `${JSON.stringify(revenueNotebook, null, 3)}\n`
   },
   {
      name: "revenue-by-country.chart",
      contentType: "application/json",
      content: `${JSON.stringify(chartDocument, null, 3)}\n`
   },
   {
      name: "monthly-revenue.dt",
      contentType: "application/json",
      content: `${JSON.stringify(dataTableDocument, null, 3)}\n`
   },
   {
      // A file inside a folder makes the Files page show breadcrumb navigation
      // and the "reports/" entry instead of a flat list.
      name: "revenue-by-month.csv",
      contentType: "text/csv",
      prefix: "reports",
      sql:
         "select strftime('%Y-%m', InvoiceDate) as month, " +
         "round(sum(Total), 2) as revenue from Invoice group by 1 order by 1"
   }
];

export const fixtureExpectations = {
   files: seedFiles.map((file) => file.name),
   catalogEntities
};
