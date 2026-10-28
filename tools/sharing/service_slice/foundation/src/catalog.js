export const categories = {
  comp: { name: 'Compositions', singular: 'Composition', path: '/compositions', number: '01', label: 'DEN DESIGNER', description: 'Small details. New possibilities. Discover prop arrangements and building blocks for your next Den.' },
  den: { name: 'Dens', singular: 'Den', path: '/dens', number: '02', label: 'COMPLETE LAYOUTS', description: 'A place for your company. Explore complete Den layouts, from quiet quarters to mission-ready headquarters.' },
  char: { name: 'Characters', singular: 'Character', path: '/characters', number: '03', label: 'CHARACTER SHARE', description: 'Every operative has a story. Find character creations to bring a new face to your company.' }
};
export const codePattern = /^[A-Za-z0-9_-]{6,32}$/;
export const fixtures = Object.keys(categories).map(kind => ({ code: 'demo-001', kind, title: `Sample ${categories[kind].singular.toLowerCase()}`, description: 'Development fixture only. This is not a community upload.', schema_version: 1, published_at: '2026-10-26T00:00:00Z' }));
export function fixtureEnabled(request, env) {
  return env.ENVIRONMENT === 'development' && env.FIXTURE_MODE === 'true' && ['localhost','127.0.0.1','[::1]'].includes(new URL(request.url).hostname);
}
