"use client";
import { useEffect } from "react";
import { motion, stagger, useAnimate } from "framer-motion";
import { cn } from "@/lib/cn";

export function TextGenerateEffect({
  words,
  className,
}: {
  words: string;
  className?: string;
}) {
  const [scope, animate] = useAnimate();
  const wordsArray = words.split(" ");

  useEffect(() => {
    animate("span", { opacity: 1 }, { duration: 1.5, delay: stagger(0.12) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <motion.h1
      ref={scope}
      className={cn("text-3xl sm:text-4xl font-semibold tracking-tight", className)}
    >
      {wordsArray.map((word, idx) => (
        <motion.span
          key={word + idx}
          className="opacity-0 inline-block mr-[0.25em]"
        >
          {word}
        </motion.span>
      ))}
    </motion.h1>
  );
}
