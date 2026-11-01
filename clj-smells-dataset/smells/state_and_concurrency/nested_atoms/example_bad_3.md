## Metadata

* **Smell name:** nested_atoms
* **Expected smell location:** Game state atom
* **Affected forms:** `atom`, `volatile!`
* **Short explanation:** Storing an atom inside another atom makes state synchronization difficult and breaks the single-source-of-truth principle.

```Clojure
(ns game.core.state)

(def initial-game-state
  {:level 1
   :score 0
   ; VALIDATION: SMELL START - nested_atoms
   ; VALIDATION: Storing a volatile inside an atom
   :player-pos (volatile! [0 0])})
   ; VALIDATION: SMELL END

(def game-state (atom initial-game-state))

(defn move-player!
  [dx dy]
  (let [pos (:player-pos @game-state)
        [x y] @pos]
    (vreset! pos [(+ x dx) (+ y dy)])))
```
