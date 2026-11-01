## Metadata

* **Smell name:** nested_atoms
* **Expected smell location:** UI state atom initialization
* **Affected forms:** `atom`
* **Short explanation:** Storing an atom inside another atom makes state synchronization difficult and breaks the single-source-of-truth principle.

```Clojure
(ns app.ui.state)

; VALIDATION: SMELL START - nested_atoms
; VALIDATION: Storing an atom inside another atom
(def app-state
  (atom {:current-page :home
         :user-profile (atom {:name "Bob" :age 30})}))
; VALIDATION: SMELL END

(defn update-age!
  [new-age]
  (swap! (:user-profile @app-state) assoc :age new-age))
```
