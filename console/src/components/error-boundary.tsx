"use client";

import React from "react";
import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
    children: React.ReactNode;
}

interface State {
    hasError: boolean;
    error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="flex flex-col items-center justify-center gap-4 py-20">
                    <AlertCircle className="h-12 w-12 text-destructive/50" />
                    <div className="text-center">
                        <h2 className="text-lg font-semibold">Something went wrong</h2>
                        <p className="mt-1 text-sm text-muted-foreground">
                            {this.state.error?.message ?? "An unexpected error occurred."}
                        </p>
                    </div>
                    <Button variant="outline" onClick={() => this.setState({ hasError: false, error: null })}>
                        Try again
                    </Button>
                </div>
            );
        }
        return this.props.children;
    }
}
