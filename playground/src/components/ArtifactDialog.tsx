import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import Icon from "@/components/Icon";

export default function ArtifactDialog({
    title,
    children,
    onClose,
}: {
    title: string;
    children: ReactNode;
    onClose: () => void;
}) {
    const ref = useRef<HTMLDialogElement>(null);
    useEffect(() => {
        const dialog = ref.current;
        dialog?.showModal();
        return () => dialog?.close();
    }, []);
    return (
        <dialog
            ref={ref}
            className="dialog m-auto max-h-[85svh] w-[min(640px,calc(100%-32px))] rounded-xl border border-border-default bg-surface-default p-0 text-text-primary"
            onCancel={onClose}
            onClick={(event) => {
                if (event.target === event.currentTarget) onClose();
            }}
            aria-labelledby="artifact-title"
        >
            <div className="flex items-center justify-between gap-4 border-b border-border-default py-2 pr-2 pl-6 max-md:pl-4">
                <h2 id="artifact-title" className="text-base font-semibold">
                    {title}
                </h2>
                <button
                    type="button"
                    className="btn btn-ghost btn-icon"
                    aria-label="Close dialog"
                    onClick={onClose}
                >
                    <Icon name="x" />
                </button>
            </div>
            <div className="flex flex-col gap-4 p-6 max-md:p-4">{children}</div>
        </dialog>
    );
}
