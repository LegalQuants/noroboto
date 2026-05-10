// Minimal stub for @hocuspocus/provider. Superdoc only instantiates this when
// collaborative editing is enabled, which we never do. A no-op class is enough
// to satisfy module resolution and keep websocket/y-protocols code out of the
// browser bundle.

class NoopProvider {
  constructor() {}
  on() {}
  off() {}
  destroy() {}
  disconnect() {}
  connect() {}
}

export class HocuspocusProvider extends NoopProvider {}
export class HocuspocusProviderWebsocket extends NoopProvider {}

export default { HocuspocusProvider, HocuspocusProviderWebsocket };
