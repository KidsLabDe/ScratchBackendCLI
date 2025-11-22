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
     * Login bei Scratch und Token an Backend senden
     * @param {string} username - Scratch Benutzername
     * @param {string} password - Scratch Passwort (wird nicht gespeichert!)
     */
    async login(username, password) {
        try {
            // 1. CSRF Token von Scratch holen
            const csrfResponse = await fetch('https://scratch.mit.edu/csrf_token/', {
                credentials: 'include'
            });

            // CSRF Token aus Cookie extrahieren
            const cookies = document.cookie.split(';');
            let csrfToken = '';
            for (const cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'scratchcsrftoken') {
                    csrfToken = value;
                    break;
                }
            }

            if (!csrfToken) {
                throw new Error('Konnte CSRF-Token nicht abrufen');
            }

            // 2. Login bei Scratch
            const loginResponse = await fetch('https://scratch.mit.edu/accounts/login/', {
                method: 'POST',
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    username: username,
                    password: password,
                    useMessages: true
                })
            });

            if (!loginResponse.ok) {
                throw new Error(`Login fehlgeschlagen: ${loginResponse.status}`);
            }

            const result = await loginResponse.json();

            if (!result || !result[0] || !result[0].username) {
                const msg = result?.[0]?.msg || 'Unbekannter Fehler';
                throw new Error(`Login fehlgeschlagen: ${msg}`);
            }

            // 3. Session-Daten extrahieren (NICHT das Passwort!)
            const sessionData = {
                username: result[0].username,
                token: result[0].token || '',
                // Session-ID aus Cookie
                sessionId: this._getCookie('scratchsessionsid') || ''
            };

            // 4. Nur Session-Token an dein Backend senden
            const backendResponse = await fetch(this.backendUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(sessionData)
            });

            if (!backendResponse.ok) {
                throw new Error('Backend-Fehler beim Speichern der Session');
            }

            const backendResult = await backendResponse.json();

            this.onSuccess({
                username: sessionData.username,
                ...backendResult
            });

            return sessionData.username;

        } catch (error) {
            this.onError(error);
            throw error;
        }
    }

    /**
     * Cookie-Wert auslesen
     */
    _getCookie(name) {
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [cookieName, cookieValue] = cookie.trim().split('=');
            if (cookieName === name) {
                return cookieValue;
            }
        }
        return null;
    }
}

// Export für Module
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ScratchAuth;
}
