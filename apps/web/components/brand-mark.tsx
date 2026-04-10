import Image from "next/image";

interface BrandMarkProps {
  compact?: boolean;
  showSlogan?: boolean;
}

export function BrandMark({ compact = false, showSlogan = true }: BrandMarkProps) {
  const width = compact ? 98 : 164;
  const height = compact ? 132 : 220;

  return (
    <div className="inline-flex flex-col items-start">
      <Image
        src="/branding/respiro-3-logo.png"
        alt="Respiro Integral"
        width={width}
        height={height}
        className="h-auto w-auto"
        priority
      />
      {showSlogan ? (
        <p className="mt-2 text-[1.02rem] font-slogan font-semibold text-brand-600">Tranqui, tómate un respiro</p>
      ) : null}
    </div>
  );
}