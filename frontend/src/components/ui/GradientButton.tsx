import React, { forwardRef } from "react";
import { Button, ButtonProps } from "./Button";

export interface GradientButtonProps extends Omit<ButtonProps, "variant"> {}

/**
 * Backward-compatible adapter for Button with variant="gradient".
 */
export const GradientButton = forwardRef<HTMLButtonElement, GradientButtonProps>(
    ({ children, ...props }, ref) => {
        return (
            <Button ref={ref} variant="gradient" {...props}>
                {children}
            </Button>
        );
    }
);

GradientButton.displayName = "GradientButton";
