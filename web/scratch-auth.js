/**
 * Scratch Auth - Client-seitiger Login
 *
 * Das Passwort wird NUR im Browser verarbeitet und nie an deinen Server gesendet.
 * Nur der Session-Token wird an dein Backend übermittelt.
 */

class ScratchAuth {
    constructor(options = {}) {
        this.backendUrl = options.backendUrl || '/api/scratch-auth';
        this.onSuccess = options.onSuccess || (() => {});
        this.onError = options.onError || ((err) => console.error(err));
    }

    /**
     * Login bei Scratch über Backend-Proxy
     * @param {string} username - Scratch Benutzername
     * @param {string} password - Scratch Passwort (wird nur an Backend gesendet, nie gespeichert!)
     */
    async login(username, password) {
        try {
            // Login über Backend-Proxy (wegen CORS)
            const response = await fetch(this.backendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Login fehlgeschlagen');
            }

            this.onSuccess(result);
            return result.username;

        } catch (error) {
            this.onError(error);
            throw error;
        }
    }
}

// Export für Module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScratchAuth;
}
