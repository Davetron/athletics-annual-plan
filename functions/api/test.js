export function onRequest(context) {
  return new Response(JSON.stringify({ message: "Hello from function!" }), {
    headers: { "Content-Type": "application/json" }
  });
}
