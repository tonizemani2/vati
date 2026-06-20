import { authorized, json } from "./_understandAuth";

export const onRequestGet = async ({ request }: { request: Request }) => {
  if (!authorized(request)) return json(403, { error: "invalid token" });
  return json(200, {});
};
