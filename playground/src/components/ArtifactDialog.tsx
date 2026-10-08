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
            className="artifact-dialog"
            onCancel={onClose}
            onClick={(event) => {
                if (event.target === event.currentTarget) onClose();
            }}
            aria-labelledby="artifact-title"
        >
            <div className="dialog-header">
                <h2 id="artifact-title">{title}</h2>
                <button
                    className="icon-button"
                    aria-label="Close dialog"
                    onClick={onClose}
                >
                    <Icon name="close" />
                </button>
            </div>
            <div className="dialog-body">{children}</div>
        </dialog>
    );
}
