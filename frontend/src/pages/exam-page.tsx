import { useState } from "react"
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { Play, CheckCircle2, Camera } from "lucide-react"

export function ExamPage() {
  const [isRunning, setIsRunning] = useState(false)
  const [testsPassed, setTestsPassed] = useState(false)

  const handleRunTests = () => {
    setIsRunning(true)
    setTimeout(() => {
      setIsRunning(false)
      setTestsPassed(true)
    }, 1200)
  }

  return (
    <div className="flex h-full flex-col">
      <ResizablePanelGroup orientation="horizontal" className="flex-1">
        {/* Left Panel: Exercise Specs & Video Telemetry */}
        <ResizablePanel defaultSize={35} minSize={25} className="flex flex-col border-r bg-card/60 p-4 overflow-y-auto">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Badge variant="outline" className="text-xs">
                Desafío AST #284
              </Badge>
              <Badge className="bg-primary/10 text-primary border-primary/20 text-xs">
                Puntaje Requerido: 80%
              </Badge>
            </div>

            <div>
              <h2 className="text-lg font-bold text-foreground">
                Inversión de Árbol Binario y Detección de Ciclos
              </h2>
              <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                Implementá una función en Python que reciba la raíz de un árbol binario y devuelva la estructura invertida en espejo con complejidad temporal $O(N)$ y espacio auxiliar $O(H)$.
              </p>
            </div>

            <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-muted-foreground block">
                Restricciones de Integridad
              </span>
              <ul className="text-xs space-y-1.5 text-muted-foreground list-disc list-inside">
                <li>El portapapeles y pegado de código externo está bloqueado.</li>
                <li>Cambio de pestaña activa generará advertencia inmediata.</li>
                <li>Análisis AST comprobará que no uses `eval` ni librerías no permitidas.</li>
              </ul>
            </div>

            {/* Camera Preview */}
            <div className="rounded-lg border bg-background p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold flex items-center gap-1.5 text-foreground">
                  <Camera className="h-3.5 w-3.5 text-primary" />
                  Prueba de Vida Activa
                </span>
                <span className="text-[10px] font-bold text-primary">30 FPS</span>
              </div>
              <div className="aspect-video w-full rounded-md bg-muted flex flex-col items-center justify-center text-muted-foreground text-xs relative overflow-hidden border">
                <div className="absolute top-2 left-2 flex items-center gap-1 bg-black/60 text-white rounded px-1.5 py-0.5 text-[9px]">
                  <span className="h-1.5 w-1.5 rounded-full bg-destructive animate-pulse" />
                  REC
                </div>
                <span>Cámara Web Transmitiendo</span>
                <span className="text-[10px] text-muted-foreground/80 mt-0.5">Rostro centrado (Confianza: 98.4%)</span>
              </div>
            </div>
          </div>
        </ResizablePanel>

        <ResizableHandle withHandle />

        {/* Right Panel: Code Editor + Docker Test Terminal */}
        <ResizablePanel defaultSize={65} minSize={40} className="flex flex-col">
          <ResizablePanelGroup orientation="vertical">
            {/* Top: Code Editor */}
            <ResizablePanel defaultSize={60} minSize={30} className="flex flex-col border-b bg-muted/10">
              <div className="flex h-10 items-center justify-between border-b bg-card px-4">
                <div className="flex items-center gap-2 text-xs font-mono font-medium text-muted-foreground">
                  <span>solution.py</span>
                  <span className="text-border">|</span>
                  <span>Python 3.12 (Isolated Docker)</span>
                </div>
                <Button size="sm" onClick={handleRunTests} disabled={isRunning} className="h-7 text-xs gap-1.5">
                  <Play className="h-3 w-3 fill-current" />
                  <span>{isRunning ? "Ejecutando..." : "Ejecutar Tests"}</span>
                </Button>
              </div>

              <div className="flex-1 p-4 font-mono text-xs overflow-auto bg-background/50 leading-relaxed">
                <pre className="text-foreground">
{`# Implementación requerida por el desafío
class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

def invert_tree(root: TreeNode) -> TreeNode:
    if not root:
        return None
    
    # Invertir subárboles recursivamente
    root.left, root.right = invert_tree(root.right), invert_tree(root.left)
    return root
`}
                </pre>
              </div>
            </ResizablePanel>

            <ResizableHandle withHandle />

            {/* Bottom: Test Runner Results */}
            <ResizablePanel defaultSize={40} minSize={20} className="flex flex-col bg-card/80">
              <Tabs defaultValue="tests" className="flex flex-col h-full">
                <div className="flex h-10 items-center justify-between border-b px-4">
                  <TabsList className="h-7 text-xs">
                    <TabsTrigger value="tests" className="text-xs h-6">Resultados Pytest</TabsTrigger>
                    <TabsTrigger value="ast" className="text-xs h-6">Métricas AST</TabsTrigger>
                  </TabsList>
                  {testsPassed && (
                    <Badge className="bg-primary/10 text-primary border-primary/20 text-[10px]">
                      5 / 5 Casos Aprobados
                    </Badge>
                  )}
                </div>

                <TabsContent value="tests" className="flex-1 p-4 font-mono text-xs overflow-auto m-0">
                  {isRunning ? (
                    <div className="text-muted-foreground animate-pulse">
                      Iniciando contenedor Docker efímero... ejecutando pytest tests/test_solution.py...
                    </div>
                  ) : testsPassed ? (
                    <div className="space-y-1.5 text-foreground">
                      <div className="text-primary font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>test_invert_tree_balanced ................... PASSED [20%]</span>
                      </div>
                      <div className="text-primary font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>test_invert_tree_single_node ................ PASSED [40%]</span>
                      </div>
                      <div className="text-primary font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>test_invert_tree_empty ...................... PASSED [60%]</span>
                      </div>
                      <div className="text-primary font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>test_invert_tree_large_depth ................ PASSED [80%]</span>
                      </div>
                      <div className="text-primary font-semibold flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4" />
                        <span>test_ast_cyclomatic_complexity .............. PASSED [100%]</span>
                      </div>
                      <p className="pt-2 text-xs text-muted-foreground border-t font-sans">
                        Tiempo total de ejecución en sandbox: <strong>0.18s</strong> • Memoria pico: <strong>14.2 MB</strong>
                      </p>
                    </div>
                  ) : (
                    <div className="text-muted-foreground">
                      Haz clic en &quot;Ejecutar Tests&quot; para compilar tu código en el sandbox aislado y verificar los casos de prueba.
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="ast" className="flex-1 p-4 text-xs m-0 text-muted-foreground space-y-2">
                  <p>Complejidad ciclomática detectada: <strong>2</strong> (Aceptable &lt; 10).</p>
                  <p>Profundidad del árbol de sintaxis abstracta: <strong>4 niveles</strong>.</p>
                  <p>Llamadas prohibidas: <strong>0 detectadas</strong>.</p>
                </TabsContent>
              </Tabs>
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  )
}
