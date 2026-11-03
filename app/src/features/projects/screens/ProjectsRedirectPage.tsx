import { Navigate } from "react-router-dom";

/**
 * Legacy route redirect.
 *
 * The standalone projects page was merged into the home dashboard. Keep this
 * route registered so any existing `/projects` links and bookmarks resolve to
 * the home page instead of a 404.
 */
const ProjectsRedirectPage = () => <Navigate to="/" replace />;

export default ProjectsRedirectPage;
