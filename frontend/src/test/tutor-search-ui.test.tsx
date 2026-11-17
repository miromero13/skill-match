import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import { BrowserRouter } from "react-router-dom"
import { SearchPage } from "@/pages/search-page"
import { useTutorSearchStore } from "@/stores/search-store"
import { searchService } from "@/services/search-service"
import type { TutorSearchResult } from "@/types/search"

vi.mock("@/services/search-service", () => ({
  searchService: {
    searchTutors: vi.fn(),
    getCategories: vi.fn().mockResolvedValue([]),
    getSkills: vi.fn().mockResolvedValue([]),
  },
}))

const mockTutors: TutorSearchResult[] = [
  {
    id: "tutor-1",
    full_name: "Ana Python Pro",
    avatar_url: null,
    bio: "Experta en FastAPI y PyTorch",
    location_label: "La Paz Centro",
    latitude: -16.505,
    longitude: -68.14,
    exchange_modality: "BOTH",
    presencial_radius_km: 20,
    distance_km: 1.2,
    rating: 5.0,
    total_reviews: 8,
    has_verified_skills: true,
    skills: [
      {
        id: "skill-1",
        skill_id: "sk-python",
        skill_name: "Python y Backend",
        category_id: "cat-prog",
        category_name: "Programación y Software",
        declared_level: "EXPERT",
        years_of_experience: 6,
        description: "6 años desarrollando backend",
        accepts_points: true,
        hourly_points_rate: 30,
        status: "VERIFICADA",
        is_verified: true,
      },
    ],
    created_at: new Date().toISOString(),
  },
]

describe("SearchPage & Tutor Search UI (HU-20 / SM-32)", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(searchService.searchTutors).mockResolvedValue({
      statuscode: 200,
      message: "Se encontraron 1 instructores compatibles.",
      data: mockTutors,
      count: 1,
    })
    useTutorSearchStore.setState({
      filters: {
        query: "",
        category_id: "",
        skill_id: "",
        min_level: "",
        verified_only: false,
        modality: undefined,
        max_distance: undefined,
        sort_by: "reputation",
        page: 1,
        page_size: 12,
      },
      tutors: mockTutors,
      totalCount: 1,
      isLoading: false,
      error: null,
      apiMessage: "Se encontraron 1 instructores compatibles.",
      categories: [
        {
          id: "cat-prog",
          name: "Programación y Software",
          slug: "programacion-y-software",
          description: null,
          is_active: true,
        },
      ],
      skills: [],
    })
  })

  it("renders the main search page with heading, search input and quick filters", () => {
    render(
      <BrowserRouter>
        <SearchPage />
      </BrowserRouter>
    )

    expect(screen.getByRole("heading", { name: /explorar instructores/i })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/buscar por instructor, habilidad/i)).toBeInTheDocument()
    expect(screen.getByText(/solo verificados ia/i)).toBeInTheDocument()
  })

  it("renders tutor card with details, IA verification badge and skills", async () => {
    render(
      <BrowserRouter>
        <SearchPage />
      </BrowserRouter>
    )

    expect(await screen.findByText("Ana Python Pro")).toBeInTheDocument()
    expect(screen.getByText("Python y Backend")).toBeInTheDocument()
    expect(screen.getByText("30 pts/hr")).toBeInTheDocument()
    expect(screen.getByText("1.2 km")).toBeInTheDocument()
  })

  it("opens swap proposal dialog when clicking Intercambio", async () => {
    render(
      <BrowserRouter>
        <SearchPage />
      </BrowserRouter>
    )

    const swapBtn = await screen.findByRole("button", { name: /intercambio/i })
    fireEvent.click(swapBtn)

    expect(
      await screen.findByRole("heading", { name: /proponer intercambio a ana python pro/i })
    ).toBeInTheDocument()
  })

  it("displays empty state when no tutors match", async () => {
    vi.mocked(searchService.searchTutors).mockResolvedValueOnce({
      statuscode: 200,
      message: "Se encontraron 0 instructores compatibles.",
      data: [],
      count: 0,
    })

    render(
      <BrowserRouter>
        <SearchPage />
      </BrowserRouter>
    )

    expect(
      await screen.findByText(/no se encontraron instructores compatibles/i)
    ).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /restablecer todos los filtros/i })).toBeInTheDocument()
  })
})
