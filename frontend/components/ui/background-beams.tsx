"use client";
import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/cn";

const BEAMS = [
  { x1: "0%",  y1: "80%", x2: "100%", y2: "20%", grad: "url(#bgb-1)", delay: 0,   dur: 4   },
  { x1: "15%", y1: "0%",  x2: "85%",  y2: "100%", grad: "url(#bgb-2)", delay: 1,   dur: 5   },
  { x1: "0%",  y1: "40%", x2: "100%", y2: "60%",  grad: "url(#bgb-3)", delay: 2,   dur: 6   },
  { x1: "5%",  y1: "100%",x2: "95%",  y2: "0%",   grad: "url(#bgb-1)", delay: 0.5, dur: 4.5 },
  { x1: "50%", y1: "0%",  x2: "50%",  y2: "100%", grad: "url(#bgb-2)", delay: 1.5, dur: 5.5 },
];

export const BackgroundBeams = React.memo(({ className }: { className?: string }) => (
  <div className={cn("absolute inset-0 overflow-hidden pointer-events-none", className)}>
    <div className="absolute -top-20 left-1/4 w-[500px] h-[300px] rounded-full bg-brand/10 blur-3xl" />
    <div className="absolute -top-10 right-1/4 w-[400px] h-[250px] rounded-full bg-brand-emerald/5 blur-3xl" />
    <svg
      className="absolute inset-0 h-full w-full"
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="xMidYMid slice"
    >
      <defs>
        <linearGradient id="bgb-1" x1="0%" y1="100%" x2="100%" y2="0%">
          <stop offset="0%"   stopColor="#5b9dff" stopOpacity="0" />
          <stop offset="40%"  stopColor="#5b9dff" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#34d399" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="bgb-2" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%"   stopColor="#34d399" stopOpacity="0" />
          <stop offset="50%"  stopColor="#34d399" stopOpacity="0.15" />
          <stop offset="100%" stopColor="#5b9dff" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="bgb-3" x1="100%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%"   stopColor="#5b9dff" stopOpacity="0" />
          <stop offset="50%"  stopColor="#5b9dff" stopOpacity="0.1" />
          <stop offset="100%" stopColor="#5b9dff" stopOpacity="0" />
        </linearGradient>
      </defs>
      {BEAMS.map(({ x1, y1, x2, y2, grad, delay, dur }, i) => (
        <motion.line
          key={i}
          x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={grad}
          strokeWidth="1.5"
          initial={{ opacity: 0 }}
          animate={{ opacity: [0, 1, 0] }}
          transition={{ duration: dur, delay, repeat: Infinity, repeatDelay: 1 }}
        />
      ))}
    </svg>
  </div>
));
BackgroundBeams.displayName = "BackgroundBeams";
