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

export function sortCategoriesByPath(
  categories: Category[],
): Array<{ category: Category; label: string }> {
  return categories
    .map((category) => ({
      category,
      label: categoryPath(category, categories),
    }))
    .sort((a, b) => a.label.localeCompare(b.label, "es"))
}

export function filterSkillsByCategory<T extends { category_id?: string }>(
  skills: T[],
  categoryId: string,
  categories: Category[],
): T[] {
  if (!categoryId || categories.length === 0) return skills
  return skills.filter((skill) => {
    if (!skill.category_id) return true
    if (skill.category_id === categoryId) return true
    const skillCategory = categories.find((cat) => cat.id === skill.category_id)
    return skillCategory ? isCategoryWithin(skillCategory, categoryId, categories) : false
  })
}
