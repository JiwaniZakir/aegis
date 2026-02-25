"use client";

import { AlertCircle, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface QueryErrorProps {
    message?: string;
    onRetry?: () => void;
}

export function QueryError({ message = "Failed to load data.", onRetry }: QueryErrorProps) {
    return (
        <Card>
            <CardContent className="flex flex-col items-center justify-center gap-3 py-8">
                <AlertCircle className="h-8 w-8 text-destructive/60" />
                <p className="text-sm text-muted-foreground">{message}</p>
                {onRetry && (
                    <Button variant="ghost" size="sm" onClick={onRetry}>
                        <RefreshCw className="mr-2 h-4 w-4" />
                        Retry
                    </Button>
                )}
            </CardContent>
        </Card>
    );
}
