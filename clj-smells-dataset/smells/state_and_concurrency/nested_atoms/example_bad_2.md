## Metadata

* **Smell name:** nested_atoms
* **Expected smell location:** Session management atom
* **Affected forms:** `atom`
* **Short explanation:** Storing an atom inside another atom makes state synchronization difficult and breaks the single-source-of-truth principle.

```Clojure
(ns app.session.manager)

(defn create-session
  [user-id]
  {:user-id user-id
   :last-active (System/currentTimeMillis)
   ; VALIDATION: SMELL START - nested_atoms
   ; VALIDATION: Storing an atom inside a map that goes into an atom
   :preferences (atom {:theme :dark})})
   ; VALIDATION: SMELL END

(def active-sessions (atom {}))

(defn login-user!
  [user-id]
  (swap! active-sessions assoc user-id (create-session user-id)))
```
