import { MatchSuggestions } from "@/components/matches/matches-suggestions"

export function MatchesPage() {
    // Reutiliza la sección del feed en modo de listado completo.
    return (
        <main className="mx-auto w-full max-w-5xl p-4 pb-20 md:p-6">
            <MatchSuggestions />
        </main>
    )
}