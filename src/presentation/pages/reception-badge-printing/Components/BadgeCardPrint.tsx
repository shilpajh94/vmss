import { QRCodeSVG } from 'qrcode.react'
import type { BadgeCard } from '../../../../domain/entities/checkin-schema'

const DASH = '-'

// Hidden on screen, shown alone by the `@media print` rules in index.css.
// Follows the "Visitor ID card" reference: lanyard slot, dotted border, header
// band, photo frame, wavy footer. The QR (signed badge token, accepted by the
// badge scan page) sits where the reference has a barcode. Colours are theme tokens.
export function BadgeCardPrint({ badge }: { badge: BadgeCard }) {
  const rows: Array<[string, string]> = [
    ['Name', badge.visitorName || DASH],
    ['Purpose', badge.purpose || DASH],
    ['Meet To', badge.hostName || DASH],
  ]

  return (
    <div id="badge-print-root" aria-hidden="true" className="hidden">
      <div className="badge-card relative overflow-hidden rounded-[3mm] border-[0.6mm] border-dotted border-admin-accent bg-admin-accent text-text">
        {/* Lanyard slot */}
        <div className="absolute left-1/2 top-[1.5mm] h-[3mm] w-[12mm] -translate-x-1/2 rounded-full border border-border-strong bg-surface" />

        {/* Header band */}
        <div className="mt-[6mm] bg-secondary-accent-soft py-[1.5mm] text-center font-display text-[14px] font-bold tracking-wide text-admin-accent">
          VISITOR ID CARD
        </div>

        {/* White body with wavy teal footer */}
        <div className="relative bg-surface">
          <div className="flex gap-[3mm] px-[4mm] pt-[3mm] pb-[33mm]">
            <dl className="flex flex-1 flex-col justify-center gap-[1.5mm] font-body text-[10px]">
              {rows.map(([label, value]) => (
                <div key={label} className="flex gap-[1.5mm]">
                  <dt className="w-[14mm] shrink-0 font-bold">{label}</dt>
                  <dd className="break-words">: {value}</dd>
                </div>
              ))}
            </dl>
            {badge.photoUrl ? (
              <img src={badge.photoUrl} alt="" className="h-[28mm] w-[26mm] shrink-0 border-[0.5mm] border-admin-accent object-cover" />
            ) : (
              <div className="h-[28mm] w-[26mm] shrink-0 border-[0.5mm] border-admin-accent bg-surface-muted" />
            )}
          </div>

          <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="absolute bottom-0 left-0 h-[30mm] w-full" aria-hidden="true">
            <path d="M0 14 C 25 2, 45 30, 100 8 L100 40 L0 40 Z" fill="var(--color-admin-accent)" />
          </svg>
          {/* Plain white box, 4-module quiet zone, level M, drawn at 256 units (SVG) and scaled to 27mm: stays sharp in print. */}
          <div className="absolute bottom-[2mm] left-[3mm] bg-white">
            <QRCodeSVG
              value={badge.token}
              size={256}
              level="M"
              marginSize={4}
              bgColor="#ffffff"
              fgColor="#000000"
              style={{ width: '27mm', height: '27mm', display: 'block' }}
            />
          </div>
          <span className="absolute bottom-[4mm] right-[4mm] w-[34mm] text-right font-body text-[8px] font-semibold text-on-accent">
            Scan to check out
          </span>
        </div>
      </div>
    </div>
  )
}
