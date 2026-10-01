import { RouterProvider } from "react-router";
import Providers from "@/app/providers.tsx";
import { router } from "@/app/router.tsx";

function App() {
    return (
        <Providers>
            <RouterProvider router={router} />
        </Providers>
    );
}

export default App;
