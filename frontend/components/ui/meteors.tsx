"use client";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

interface MeteorStyle {
  top: string;
  left: string;
  width: string;
  animationDelay: string;
  animationDuration: string;
}

export function Meteors({
  number = 20,
  className,
}: {
  number?: number;
  className?: string;
}) {
  const [styles, setStyles] = useState<MeteorStyle[]>([]);

  useEffect(() => {
    setStyles(
      Array.from({ length: number }, () => ({
        top: `${Math.floor(Math.random() * 100)}%`,
        left: `${Math.floor(Math.random() * 100)}%`,
        width: `${Math.floor(Math.random() * 80 + 40)}px`,
        animationDelay: `${(Math.random() * 4).toFixed(2)}s`,
        animationDuration: `${Math.floor(Math.random() * 6 + 4)}s`,
      }))
    );
  }, [number]);

  return (
    <>
      {styles.map((style, idx) => (
        <span
          key={idx}
          className={cn(
            "animate-meteor absolute h-px rounded-full",
            "bg-gradient-to-r from-brand/50 via-brand/30 to-transparent",
            "rotate-[215deg] opacity-0",
            className
          )}
          style={style}
        />
      ))}
    </>
  );
}
