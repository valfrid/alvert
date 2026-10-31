// Serverar den statiska bloggen och bilderna från R2.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Bilder: /img/<nyckel> hämtas från R2-bucketen
    if (path.startsWith("/img/")) {
      const key = decodeURIComponent(path.slice(5));
      const obj = await env.IMAGES.get(key);
      if (!obj) return new Response("Bilden finns inte", { status: 404 });
      const headers = new Headers();
      obj.writeHttpMetadata(headers);
      headers.set("etag", obj.httpEtag);
      headers.set("cache-control", "public, max-age=31536000, immutable");
      return new Response(obj.body, { headers });
    }

    // Mappar: /2021/july/ -> /2021/july/index.html
    if (path.endsWith("/")) {
      return env.ASSETS.fetch(new Request(new URL(path + "index.html", url), request));
    }

    // /2021/july (utan snedstreck) -> /2021/july/
    const last = path.split("/").pop();
    if (!last.includes(".")) {
      return Response.redirect(new URL(path + "/" + url.search, url).toString(), 301);
    }

    return env.ASSETS.fetch(request);
  },
};
