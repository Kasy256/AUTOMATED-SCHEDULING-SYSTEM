import * as Sentry from "@sentry/react";
import type { Breadcrumb, ErrorEvent } from "@sentry/react";

// Invitation and confirmation links carry their token in the query string.
function withoutQuery(url: string): string {
  return url.split("?")[0] ?? url;
}

function scrubBreadcrumb(crumb: Breadcrumb): Breadcrumb {
  const url: unknown = crumb.data?.url;
  if (typeof url !== "string") return crumb;
  return { ...crumb, data: { ...crumb.data, url: withoutQuery(url) } };
}

export function scrubEvent(event: ErrorEvent): ErrorEvent {
  const scrubbed: ErrorEvent = { ...event };
  delete scrubbed.user;
  if (event.request) {
    const request = { ...event.request };
    delete request.cookies;
    delete request.headers;
    delete request.query_string;
    if (request.url) request.url = withoutQuery(request.url);
    scrubbed.request = request;
  }
  if (event.breadcrumbs)
    scrubbed.breadcrumbs = event.breadcrumbs.map(scrubBreadcrumb);
  return scrubbed;
}

export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN;
  if (!dsn) return;
  Sentry.init({
    dsn,
    environment: import.meta.env.VITE_DEPLOY_ENV,
    release: import.meta.env.VITE_RELEASE,
    dataCollection: {
      userInfo: false,
      cookies: false,
      httpHeaders: false,
      httpBodies: [],
      urlQueryParams: false,
    },
    beforeSend: scrubEvent,
    beforeBreadcrumb: scrubBreadcrumb,
  });
}
