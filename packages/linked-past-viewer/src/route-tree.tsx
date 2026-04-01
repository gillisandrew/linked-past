import {
  createRootRoute,
  createRoute,
  Outlet,
} from "@tanstack/react-router";
import { ViewerLayout } from "./components/viewer-layout";

const rootRoute = createRootRoute({
  component: () => <Outlet />,
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: ViewerLayout,
});

export const routeTree = rootRoute.addChildren([indexRoute]);
