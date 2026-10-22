import heroPng from '../../assets/images/lobby-hero.png'
import heroAvif768 from '../../assets/images/lobby-hero-768.avif'
import heroAvif1536 from '../../assets/images/lobby-hero-1536.avif'
import heroWebp768 from '../../assets/images/lobby-hero-768.webp'
import heroWebp1536 from '../../assets/images/lobby-hero-1536.webp'

// The lobby photo behind the public and sign-in pages. A phone gets a
// 768px AVIF (about 15 kB) or WebP instead of the 1.3 MB PNG, which stays only
// as the fallback for a browser with neither (app-performance "Public Pages
// Stay Within a Download Budget"). It is the page's largest paint, so it is
// fetched at high priority. Purely decorative: no alt text.
export function HeroImage({ className = 'size-full object-cover' }: { className?: string }) {
  return (
    <picture>
      <source type="image/avif" srcSet={`${heroAvif768} 768w, ${heroAvif1536} 1536w`} sizes="100vw" />
      <source type="image/webp" srcSet={`${heroWebp768} 768w, ${heroWebp1536} 1536w`} sizes="100vw" />
      <img src={heroPng} alt="" className={className} fetchPriority="high" decoding="async" />
    </picture>
  )
}
