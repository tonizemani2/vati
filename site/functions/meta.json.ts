import { privateAsset, type PagesEnv } from "./_understandAuth";

export const onRequestGet = async ({
  request,
  env,
}: {
  request: Request;
  env: PagesEnv;
}) => privateAsset(request, env, "/understand-data/meta.json");
