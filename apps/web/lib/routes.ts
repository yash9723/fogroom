/**
 * App routes. Entity pages take the id as a query parameter (not a dynamic path segment)
 * so the frontend can be built as a static export and served by the API (Render deploy).
 */
const q = (path: string, id: string) => `${path}?id=${encodeURIComponent(id)}`;

export const routes = {
  exercise: (roomId: string) => q("/exercises/room", roomId),
  traineeExercise: (roomId: string) => q("/exercise/room", roomId),
  aar: (roomId: string) => q("/aar/report", roomId),
  aarPrint: (roomId: string) => q("/aar/print", roomId),
  scenario: (id: string) => q("/scenarios/edit", id),
};
