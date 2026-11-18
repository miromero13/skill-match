import type { Category } from "@/types/catalog"

export function categoryPath(category: Category, categories: Category[]): string {
  const names: string[] = []
  const visited = new Set<string>()
  let current: Category | undefined = category
  while (current && !visited.has(current.id)) {
    names.unshift(current.name)
    visited.add(current.id)
    current = categories.find((item) => item.id === current?.parent_id)
  }
  return names.join(" / ")
}

export function isCategoryWithin(category: Category, ancestorId: string, categories: Category[]): boolean {
  const visited = new Set<string>()
  let current: Category | undefined = category
  while (current && !visited.has(current.id)) {
    if (current.id === ancestorId) return true
    visited.add(current.id)
    current = categories.find((item) => item.id === current?.parent_id)
  }
  return false
}
