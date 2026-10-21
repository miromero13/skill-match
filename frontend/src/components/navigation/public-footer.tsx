import { Link } from "react-router-dom"

export function PublicFooter() {
  return (
    <footer className="border-t bg-[#0B1011] text-[#8E9B9E]">
      <div className="container mx-auto max-w-7xl px-4 py-10 sm:py-16 sm:px-8">
        {/* Link columns for mobile (1 col) and desktop (4 cols) */}
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 md:grid-cols-4 text-xs">
          {/* Column 1 */}
          <div className="space-y-3">
            <h4 className="font-bold text-[11px] tracking-wider uppercase text-white">
              SKILLMATCH
            </h4>
            <ul className="space-y-2">
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Sobre la Plataforma
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Manifiesto de Trueque
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Carreras & Comunidad
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Prensa
                </span>
              </li>
            </ul>
          </div>

          {/* Column 2 */}
          <div className="space-y-3">
            <h4 className="font-bold text-[11px] tracking-wider uppercase text-white">
              TECNOLOGÍA & IA
            </h4>
            <ul className="space-y-2">
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Modelos en Contenedores
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Espectrogramas Acústicos
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Tracking Motriz con Pose
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Código de Conducta
                </span>
              </li>
            </ul>
          </div>

          {/* Column 3 */}
          <div className="space-y-3">
            <h4 className="font-bold text-[11px] tracking-wider uppercase text-white">
              SEGURIDAD & ESCROW
            </h4>
            <ul className="space-y-2">
              <li>
                <Link to="/app/wallet" className="hover:text-white transition-colors">
                  Billetera de SkillPoints
                </Link>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Política Anti-Fraude
                </span>
              </li>
              <li>
                <Link to="/app/complaints" className="hover:text-white transition-colors">
                  Resolución de Disputas
                </Link>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Protección al Consumidor
                </span>
              </li>
            </ul>
          </div>

          {/* Column 4 */}
          <div className="space-y-3">
            <h4 className="font-bold text-[11px] tracking-wider uppercase text-white">
              LEGAL & POLÍTICAS
            </h4>
            <ul className="space-y-2">
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Términos de Servicio
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Privacidad & Biometría
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Propiedad Intelectual
                </span>
              </li>
              <li>
                <span className="hover:text-white transition-colors cursor-pointer">
                  Contacto Institucional
                </span>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 sm:mt-14 border-t border-white/10 pt-6 sm:pt-8 text-[11px] text-[#67787C]">
          <p>© 2026 SkillMatch Inc. Todos los derechos reservados. Plataforma auditada con IA propia y contratos de custodia Escrow.</p>
        </div>
      </div>
    </footer>
  )
}
