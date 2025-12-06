import React from 'react';
import Layout from '../components/Layout';
import { UserCog } from 'lucide-react';

const Settings = () => {
    return (
        <Layout>
            <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
                 <div className="w-20 h-20 bg-muted rounded-full flex items-center justify-center mb-6">
                     <UserCog className="w-10 h-10 text-muted-foreground" />
                 </div>
                 <h1 className="text-3xl font-bold mb-2">Settings</h1>
                 <p className="text-muted-foreground max-w-md">
                     Configure API keys, notification preferences, and display settings.
                 </p>
            </div>
        </Layout>
    );
};

export default Settings;
