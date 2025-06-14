import re
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Set, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

class FilterOperator(Enum):
    """Filter operators for combining conditions"""
    AND = "and"
    OR = "or"
    NOT = "not"

class MatchType(Enum):
    """Types of text matching"""
    CONTAINS = "contains"
    EXACT = "exact"
    REGEX = "regex"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"

@dataclass
class FilterCondition:
    """Individual filter condition"""
    field: str  # title, summary, source_feed, etc.
    value: Any
    match_type: MatchType = MatchType.CONTAINS
    case_sensitive: bool = False
    operator: FilterOperator = FilterOperator.AND

@dataclass
class FilterRule:
    """Complete filter rule with multiple conditions"""
    name: str
    conditions: List[FilterCondition]
    priority: int = 1
    is_active: bool = True
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

class FilterEngine:
    """Advanced filtering engine for RSS articles"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.custom_filters: Dict[str, Callable] = {}
        self.compiled_regex_cache: Dict[str, re.Pattern] = {}
    
    def register_custom_filter(self, name: str, filter_func: Callable[[Dict], bool]):
        """Register a custom filter function"""
        self.custom_filters[name] = filter_func
        self.logger.info(f"Registered custom filter: {name}")
    
    def _compile_regex(self, pattern: str, flags: int = 0) -> re.Pattern:
        """Compile and cache regex patterns"""
        cache_key = f"{pattern}_{flags}"
        if cache_key not in self.compiled_regex_cache:
            try:
                self.compiled_regex_cache[cache_key] = re.compile(pattern, flags)
            except re.error as e:
                self.logger.error(f"Invalid regex pattern '{pattern}': {e}")
                raise ValueError(f"Invalid regex pattern: {e}")
        
        return self.compiled_regex_cache[cache_key]
    
    def _match_condition(self, article: Dict, condition: FilterCondition) -> bool:
        """Evaluate a single filter condition against an article"""
        # Get the field value from article
        field_value = article.get(condition.field, '')
        
        if field_value is None:
            return False
        
        # Convert to string for text operations
        field_str = str(field_value)
        condition_value = str(condition.value)
        
        # Apply case sensitivity
        if not condition.case_sensitive:
            field_str = field_str.lower()
            condition_value = condition_value.lower()
        
        # Apply matching logic based on match type
        try:
            if condition.match_type == MatchType.CONTAINS:
                return condition_value in field_str
                
            elif condition.match_type == MatchType.EXACT:
                return field_str == condition_value
                
            elif condition.match_type == MatchType.REGEX:
                flags = 0 if condition.case_sensitive else re.IGNORECASE
                pattern = self._compile_regex(condition_value, flags)
                return bool(pattern.search(field_str))
                
            elif condition.match_type == MatchType.STARTS_WITH:
                return field_str.startswith(condition_value)
                
            elif condition.match_type == MatchType.ENDS_WITH:
                return field_str.endswith(condition_value)
                
            else:
                self.logger.warning(f"Unknown match type: {condition.match_type}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error evaluating condition {condition.field} {condition.match_type} {condition.value}: {e}")
            return False
    
    def _evaluate_rule(self, article: Dict, rule: FilterRule) -> bool:
        """Evaluate a complete filter rule against an article"""
        if not rule.is_active or not rule.conditions:
            return False
        
        results = []
        
        for condition in rule.conditions:
            match_result = self._match_condition(article, condition)
            
            # Apply NOT operator if specified
            if condition.operator == FilterOperator.NOT:
                match_result = not match_result
            
            results.append((match_result, condition.operator))
        
        # Evaluate the logical expression
        return self._evaluate_logical_expression(results)
    
    def _evaluate_logical_expression(self, results: List[tuple]) -> bool:
        """Evaluate a list of (result, operator) tuples"""
        if not results:
            return False
        
        # Start with the first result
        final_result = results[0][0]
        
        # Process subsequent results with their operators
        for i in range(1, len(results)):
            result, operator = results[i]
            
            if operator == FilterOperator.AND:
                final_result = final_result and result
            elif operator == FilterOperator.OR:
                final_result = final_result or result
        
        return final_result
    
    def apply_rule(self, articles: List[Dict], rule: FilterRule) -> List[Dict]:
        """Apply a single filter rule to a list of articles"""
        if not rule.is_active:
            return articles
        
        filtered_articles = []
        
        for article in articles:
            try:
                if self._evaluate_rule(article, rule):
                    # Add metadata about which rule matched
                    article_copy = article.copy()
                    article_copy['matched_rule'] = rule.name
                    article_copy['filter_priority'] = rule.priority
                    filtered_articles.append(article_copy)
                    
            except Exception as e:
                self.logger.error(f"Error applying rule '{rule.name}' to article {article.get('link', 'unknown')}: {e}")
                continue
        
        self.logger.info(f"Rule '{rule.name}' matched {len(filtered_articles)} articles out of {len(articles)}")
        return filtered_articles
    
    def apply_rules(self, articles: List[Dict], rules: List[FilterRule]) -> List[Dict]:
        """Apply multiple filter rules to articles"""
        if not rules:
            return articles
        
        # Sort rules by priority (higher priority first)
        sorted_rules = sorted([r for r in rules if r.is_active], key=lambda x: x.priority, reverse=True)
        
        all_matches = []
        article_links_seen = set()
        
        for rule in sorted_rules:
            matches = self.apply_rule(articles, rule)
            
            # Avoid duplicates (higher priority rules take precedence)
            for article in matches:
                if article.get('link') not in article_links_seen:
                    all_matches.append(article)
                    article_links_seen.add(article.get('link'))
        
        self.logger.info(f"Applied {len(sorted_rules)} rules, found {len(all_matches)} unique matches")
        return all_matches

class PresetFilters:
    """Collection of common preset filter rules"""
    
    @staticmethod
    def awards_bagging_filter() -> FilterRule:
        """Filter for awards and bagging announcements"""
        return FilterRule(
            name="Awards/Bagging",
            conditions=[
                # Title conditions
                FilterCondition(
                    field="title",
                    value="award",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                FilterCondition(
                    field="title",
                    value="bagging",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                # Summary conditions
                FilterCondition(
                    field="summary",
                    value="award",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                FilterCondition(
                    field="summary",
                    value="bagging",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                # Link conditions
                FilterCondition(
                    field="link",
                    value="award",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                FilterCondition(
                    field="link",
                    value="bagging",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                )
            ],
            priority=5
        )
    
    @staticmethod
    def contracts_filter() -> FilterRule:
        """Filter for contract announcements"""
        return FilterRule(
            name="Contracts",
            conditions=[
                # Title condition
                FilterCondition(
                    field="title",
                    value="contract",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                # Summary condition
                FilterCondition(
                    field="summary",
                    value="contract",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                # Link condition
                FilterCondition(
                    field="link",
                    value="contract",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                )
            ],
            priority=4
        )
    
    @staticmethod
    def regulation_30_filter() -> FilterRule:
        """Filter for Regulation 30 announcements"""
        return FilterRule(
            name="Regulation 30",
            conditions=[
                # Title condition
                FilterCondition(
                    field="title",
                    value="regulation 30",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                # Summary condition
                FilterCondition(
                    field="summary",
                    value="regulation 30",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                ),
                # Link condition
                FilterCondition(
                    field="link",
                    value="regulation 30",
                    match_type=MatchType.CONTAINS,
                    case_sensitive=False,
                    operator=FilterOperator.OR
                )
            ],
            priority=3
        )
    
    @staticmethod
    def get_all_presets() -> List[FilterRule]:
        """Get all preset filter rules"""
        return [
            PresetFilters.awards_bagging_filter(),
            PresetFilters.contracts_filter(),
            PresetFilters.regulation_30_filter()
        ]
    
    @staticmethod
    def get_preset_by_name(name: str) -> FilterRule:
        """Get a specific preset filter by name"""
        presets = {
            "Awards/Bagging": PresetFilters.awards_bagging_filter(),
            "Contracts": PresetFilters.contracts_filter(),
            "Regulation 30": PresetFilters.regulation_30_filter()
        }
        return presets.get(name)

def create_keyword_filter(keywords: List[str], filter_name: str, priority: int = 1) -> FilterRule:
    """Helper function to create a simple keyword filter"""
    conditions = []
    
    for keyword in keywords:
        # Add condition for title
        conditions.append(
            FilterCondition(
                field="title",
                value=keyword,
                match_type=MatchType.CONTAINS,
                case_sensitive=False,
                operator=FilterOperator.OR
            )
        )
        # Add condition for summary
        conditions.append(
            FilterCondition(
                field="summary",
                value=keyword,
                match_type=MatchType.CONTAINS,
                case_sensitive=False,
                operator=FilterOperator.OR
            )
        )
    
    return FilterRule(
        name=filter_name,
        conditions=conditions,
        priority=priority
    )

def main():
    """Example usage of the filter engine"""
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # Sample articles for testing
    sample_articles = [
        {
            'title': 'Company ABC announces Regulation 30 disclosure',
            'summary': 'This is a regulation 30 compliance announcement regarding...',
            'link': 'http://example.com/1'
        },
        {
            'title': 'XYZ Corp wins major industry award',
            'summary': 'The company was awarded the prestigious industry recognition...',
            'link': 'http://example.com/2'
        },
        {
            'title': 'Quarterly financial results released',
            'summary': 'The company reported strong quarterly earnings with profit growth...',
            'link': 'http://example.com/3'
        }
    ]
    
    # Create filter engine
    engine = FilterEngine()
    
    # Test preset filters
    rules = PresetFilters.get_all_presets()
    
    # Apply filters
    filtered_articles = engine.apply_rules(sample_articles, rules)
    
    print(f"Found {len(filtered_articles)} matching articles:")
    for article in filtered_articles:
        print(f"- {article['title']} (matched: {article.get('matched_rule', 'unknown')})")

if __name__ == "__main__":
    main() 