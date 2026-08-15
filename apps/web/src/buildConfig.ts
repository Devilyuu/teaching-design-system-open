export function resolveBasePath(command: "build" | "serve", configuredPath?: string): string {
  if (configuredPath) return configuredPath;
  return command === "build" ? "/design/" : "/";
}
