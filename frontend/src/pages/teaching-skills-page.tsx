import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "@/components/ui/dialog"
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select"
import { useTeachingSkillStore } from "@/stores/teaching-skill-store"
import {
    declaredLevels,
    type TeachingSkill,
    type TeachingSkillPayload,
} from "@/types/teaching-skills"

const initialForm: TeachingSkillPayload = {
    skill_id: "",
    declared_level: "BEGINNER",
    years_of_experence: 0,
    description: null,
    accepts_points: false,
    hourly_points_rate: null,
}

export function TeachingSkillsPage() {
    const items = useTeachingSkillStore((s) => s.items)
    const catalog = useTeachingSkillStore((s) => s.catalog)
    const page = useTeachingSkillStore((s) => s.page)
    const total = useTeachingSkillStore((s) => s.total)
    const loading = useTeachingSkillStore((s) => s.loading)
    const saving = useTeachingSkillStore((s) => s.saving)
    const failed = useTeachingSkillStore((s) => s.failed)
    const load = useTeachingSkillStore((s) => s.load)
    const save = useTeachingSkillStore((s) => s.save)
    const remove = useTeachingSkillStore((s) => s.remove)

    const [open, setOpen] = useState(false)
    const [editingId, setEditingId] = useState<string>()
    const [deleting, setDeleting] = useState<TeachingSkill | null>(null)
    const [form, setForm] = useState<TeachingSkillPayload>(initialForm)
    const [experienceInput, setExperienceInput] = useState("0")

    useEffect(() => {
        void load(1)
    }, [load])

    function startCreate() {
        setEditingId(undefined)
        setForm({ ...initialForm })
        setExperienceInput("0")
        setOpen(true)
    }

    function startEdit(item: TeachingSkill) {
        setEditingId(item.id)
        setExperienceInput(String(item.years_of_experence))
        setForm({
            skill_id: item.skill_id,
            declared_level: item.declared_level,
            years_of_experence: item.years_of_experence,
            description: item.description,
            accepts_points: item.accepts_points,
            hourly_points_rate: item.hourly_points_rate,
        })
        setOpen(true)
    }

    return (
        <main className="mx-auto w-full max-w-4xl space-y-6 p-4 md:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <h1 className="text-2xl font-semibold">Habilidades que enseño</h1>
                    <p className="text-sm text-muted-foreground">
                        Ofrece intercambios y configura tu tarifa para clases con puntos.
                    </p>
                </div>
                <Button onClick={startCreate} disabled={loading || saving || failed}>
                    Agregar habilidad
                </Button>
            </div>

            {loading ? (
                <p role="status">Cargando habilidades…</p>
            ) : failed ? (
                <Button variant="outline" onClick={() => void load(page)}>
                    Reintentar
                </Button>
            ) : (
                <>
                    {items.length === 0 && <p>Todavía no registraste habilidades.</p>}

                    <div className="grid gap-4 sm:grid-cols-2">
                        {items.map((item) => (
                            <Card key={item.id}>
                                <CardContent className="space-y-3 p-5">
                                    <h2 className="font-semibold">{item.skill_name}</h2>
                                    <Badge variant="secondary">
                                        {item.status === "DECLARADA"
                                            ? "Declarada — sin verificar"
                                            : item.status}
                                    </Badge>
                                    <p className="text-sm">
                                        {declaredLevels.find(
                                            (level) => level.value === item.declared_level,
                                        )?.label}
                                        {" · "}{item.years_of_experence} años de experiencia
                                    </p>
                                    {item.description && (
                                        <p className="text-sm text-muted-foreground">
                                            {item.description}
                                        </p>
                                    )}
                                    <p className="text-sm">Disponible para intercambio</p>
                                    {item.accepts_points && (
                                        <p className="font-medium">
                                            Clases pagadas: {item.hourly_points_rate} puntos/hora
                                        </p>
                                    )}
                                    <div className="flex flex-wrap gap-2">
                                        <Button
                                            variant="outline"
                                            disabled={saving}
                                            onClick={() => startEdit(item)}
                                        >
                                            Editar
                                        </Button>
                                        <Button
                                            variant="destructive"
                                            disabled={saving}
                                            onClick={() => setDeleting(item)}
                                        >
                                            Eliminar
                                        </Button>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    <div className="flex items-center justify-between gap-3">
                        <Button
                            variant="outline"
                            disabled={page === 1 || saving}
                            onClick={() => void load(page - 1)}
                        >
                            Anterior
                        </Button>
                        <span className="text-sm">Página {page} · {total} habilidades</span>
                        <Button
                            variant="outline"
                            disabled={page * 20 >= total || saving}
                            onClick={() => void load(page + 1)}
                        >
                            Siguiente
                        </Button>
                    </div>
                </>
            )}

            <Dialog
                open={open}
                onOpenChange={(value) => { if (!saving) setOpen(value) }}
            >
                <DialogContent className="max-h-[85dvh] overflow-y-auto">
                    <DialogHeader>
                        <DialogTitle>
                            {editingId ? "Editar habilidad" : "Agregar habilidad"}
                        </DialogTitle>
                        <DialogDescription>
                            El nivel es declarado. Agregar una habilidad no la certifica.
                        </DialogDescription>
                    </DialogHeader>

                    <form
                        className="space-y-4"
                        onSubmit={async (event) => {
                            event.preventDefault()
                            if (!form.skill_id) return
                            if (await save(form, editingId)) setOpen(false)
                        }}
                    >
                        <div className="space-y-2">
                            <Label htmlFor="skill">Habilidad</Label>
                            <Select
                                value={form.skill_id}
                                disabled={Boolean(editingId) || saving}
                                onValueChange={(value) =>
                                    setForm((current) => ({ ...current, skill_id: value }))
                                }
                            >
                                <SelectTrigger id="skill" className="w-full">
                                    <SelectValue placeholder="Selecciona una habilidad" />
                                </SelectTrigger>
                                <SelectContent>
                                    {catalog.map((skill) => (
                                        <SelectItem key={skill.id} value={skill.id}>
                                            {skill.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            {catalog.length === 0 && (
                                <p className="text-sm text-muted-foreground">
                                    No hay habilidades activas disponibles en el catálogo.
                                </p>
                            )}
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="level">Nivel declarado</Label>
                            <Select
                                value={form.declared_level}
                                disabled={saving}
                                onValueChange={(value) => {
                                    const selected = declaredLevels.find(
                                        (level) => level.value === value,
                                    )
                                    if (selected) {
                                        setForm((current) => ({
                                            ...current, declared_level: selected.value,
                                        }))
                                    }
                                }}
                            >
                                <SelectTrigger id="level" className="w-full">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {declaredLevels.map((level) => (
                                        <SelectItem key={level.value} value={level.value}>
                                            {level.label}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="experience">Años de experiencia</Label>
                            <Input
                                id="experience"
                                type="number"
                                min={0}
                                max={60}
                                step={1}
                                required
                                disabled={saving}
                                value={experienceInput}
                                onChange={(event) => {
                                    setExperienceInput(event.target.value)
                                    setForm((current) => ({
                                        ...current,
                                        years_of_experence: Number(event.target.value),
                                    }))
                                }}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="description">Describe tu experiencia</Label>
                            <Textarea
                                id="description"
                                maxLength={2000}
                                disabled={saving}
                                value={form.description ?? ""}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current, description: event.target.value || null,
                                    }))
                                }
                            />
                        </div>

                        <div className="flex items-center justify-between gap-4">
                            <Label htmlFor="accepts-points">
                                También ofrezco clases con puntos
                            </Label>
                            <Switch
                                id="accepts-points"
                                checked={form.accepts_points}
                                disabled={saving}
                                onCheckedChange={(checked) =>
                                    setForm((current) => ({
                                        ...current,
                                        accepts_points: checked,
                                        hourly_points_rate: checked
                                            ? current.hourly_points_rate ?? 1
                                            : null,
                                    }))
                                }
                            />
                        </div>

                        {form.accepts_points && (
                            <div className="space-y-2">
                                <Label htmlFor="rate">Puntos por hora</Label>
                                <Input
                                    id="rate"
                                    type="number"
                                    min={1}
                                    max={2147483647}
                                    step={1}
                                    required
                                    disabled={saving}
                                    value={form.hourly_points_rate ?? ""}
                                    onChange={(event) =>
                                        setForm((current) => ({
                                            ...current,
                                            hourly_points_rate: event.target.value === ""
                                                ? null
                                                : Number(event.target.value),
                                        }))
                                    }
                                />
                            </div>
                        )}

                        <Button
                            type="submit"
                            className="w-full"
                            disabled={saving || !form.skill_id}
                        >
                            {saving ? "Guardando…" : "Guardar habilidad"}
                        </Button>
                    </form>
                </DialogContent>
            </Dialog>

            <Dialog
                open={deleting !== null}
                onOpenChange={(value) => { if (!value && !saving) setDeleting(null) }}
            >
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Eliminar habilidad</DialogTitle>
                        <DialogDescription>
                            ¿Deseas eliminar tu oferta de {deleting?.skill_name}?
                        </DialogDescription>
                    </DialogHeader>
                    <Button
                        variant="destructive"
                        disabled={saving}
                        onClick={async () => {
                            if (!deleting) return
                            try {
                                await remove(deleting.id)
                                setDeleting(null)
                            } catch {
                                // El cliente HTTP muestra el message del backend.
                            }
                        }}
                    >
                        {saving ? "Eliminando…" : "Confirmar eliminación"}
                    </Button>
                </DialogContent>
            </Dialog>
        </main>
    )
}
