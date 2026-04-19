"use client";
import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/cn";

interface Item {
  title: string;
  description: string;
}

export function HoverEffect({
  items,
  className,
}: {
  items: Item[];
  className?: string;
}) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  return (
    <div className={cn("grid gap-2 sm:grid-cols-3", className)}>
      {items.map((item, idx) => (
        <div
          key={idx}
          className="relative group h-full"
          onMouseEnter={() => setHoveredIndex(idx)}
          onMouseLeave={() => setHoveredIndex(null)}
        >
          <AnimatePresence>
            {hoveredIndex === idx && (
              <motion.span
                className="absolute inset-0 h-full w-full bg-brand/10 block rounded-2xl"
                layoutId="hoverBackground"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1, transition: { duration: 0.15 } }}
                exit={{ opacity: 0, transition: { duration: 0.15, delay: 0.2 } }}
              />
            )}
          </AnimatePresence>
          <div className="panel p-5 relative z-10 h-full">
            <h3 className="font-medium">{item.title}</h3>
            <p className="text-sm text-surface-muted mt-1.5 leading-relaxed">
              {item.description}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
