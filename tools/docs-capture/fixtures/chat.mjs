/**
 * Chat fixture coordinates.
 *
 * The recorded conversation is replayed by inserting the exact rows a real run
 * wrote, so capture never needs a model credential.
 */
export const CHAT_SESSION_ID = "9c2f5a3e-7f41-5d6b-9c1a-2b3d4e5f6a7b";
export const CHAT_SESSION_NAME = "Which markets lead revenue?";
export const CHAT_QUESTION =
   "Which countries generate the most revenue in the music store, and what should I look at next?";

/**
 * Artifacts the recorded run produced, linked by fixture file name. The replay
 * seed resolves each name to the uploaded file's id so the panel can render the
 * same chart and data table as a live run.
 */
export const CHAT_ARTIFACTS = [
   {
      name: "revenue-by-country.chart",
      artifactType: "Chart",
      title: "Revenue by country"
   },
   {
      name: "monthly-revenue.dt",
      artifactType: "DataTable",
      title: "Monthly revenue"
   }
];
