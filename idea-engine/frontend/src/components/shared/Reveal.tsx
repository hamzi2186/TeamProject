import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

interface RevealProps {
  children: ReactNode;
  delay?: number;
  className?: string;
}

/**
 * Subtle functional page reveal. Timing stays within the 160-220ms range
 * and is disabled entirely when the user prefers reduced motion.
 */
export function Reveal({ children, delay = 0, className }: RevealProps) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      className={className}
      initial={false}
      animate={{ opacity: 1, y: reduceMotion ? 0 : 0 }}
      style={{ opacity: reduceMotion ? 1 : undefined }}
      exit={{ opacity: 0 }}
      transition={reduceMotion ? { duration: 0 } : { opacity: { duration: 0.18, delay }, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}